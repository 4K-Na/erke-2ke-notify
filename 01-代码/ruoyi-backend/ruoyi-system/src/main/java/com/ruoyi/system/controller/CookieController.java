package com.ruoyi.system.controller;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ruoyi.common.annotation.Log;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.enums.BusinessType;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.io.File;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.attribute.PosixFilePermission;
import java.nio.file.attribute.PosixFilePermissions;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.*;

/**
 * 2ke Cookie 管理 —— 查看到期状态、在线续期。
 *
 * <p>为什么需要这个：Cookie 是采集器的唯一凭据，约 60 天过期一次。
 * 过期后采集会静默失败，靠 Dispatcher 的巡检告警才发现。
 * 有了这个接口，可以在后台直接看到剩余天数、粘贴新 token、重启采集器，
 * 不用 SSH 上去执行脚本。
 *
 * <p>到期时间的来源：2ke 的 {@code GET /api/auth/session} 返回
 * {@code {"expires":"2026-11-21T09:07:28.464Z", ...}}，不是从 token 里解析的
 * （那个 token 是 UUID 不是 JWT，本身不含 exp）。
 */
@RestController
@RequestMapping("/system/ops/cookie")
public class CookieController extends BaseController {

    private static final String COOKIE_FILE = "/opt/jmu-2ke/2ke_cookie.json";
    private static final String SESSION_URL = "https://2ke.jmu.edu.cn/api/auth/session";
    private static final String COLLECTOR_UNIT = "2ke-hub-mysql";

    /** 与 jmu_2ke_api.py 保持一致，2ke 会校验 UA */
    private static final String UA =
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            + "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";

    private static final DateTimeFormatter FMT =
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");

    private final ObjectMapper mapper = new ObjectMapper();

    /**
     * 从 2ke_cookie.json 构造 Cookie 请求头。
     *
     * <p>这个文件里有 9 个 cookie，分属不同域名：
     * <pre>
     *   SESSION / TGC              cas.paas.jmu.edu.cn （CAS 单点登录）
     *   __access_token             .jmu.edu.cn         ← 真正决定 2ke 放行的就是它
     *   __Host-authjs.csrf-token   2ke.jmu.edu.cn
     *   __Secure-authjs.session-token  2ke.jmu.edu.cn
     *   weboffice_* / oauth2.isSkip    其他系统，与 2ke 无关
     * </pre>
     *
     * <p>实测：只带 __access_token 就能通过；只带 session-token 会 302 到登录页。
     * 所以这里按域名筛选，只发 .jmu.edu.cn 和 2ke.jmu.edu.cn 的 cookie，
     * 避免把其他系统的 cookie 也塞进去。
     */
    private String buildCookieHeader(JsonNode root) {
        JsonNode arr = root.path("cookies");
        if (!arr.isArray()) {
            return null;
        }
        StringBuilder sb = new StringBuilder();
        boolean hasAccessToken = false;

        for (JsonNode c : arr) {
            String name = c.path("name").asText("");
            String value = c.path("value").asText("");
            String domain = c.path("domain").asText("");
            if (name.isEmpty() || value.isEmpty()) {
                continue;
            }
            boolean relevant = domain.equals("2ke.jmu.edu.cn")
                    || domain.equals(".jmu.edu.cn")
                    || domain.equals("jmu.edu.cn");
            if (!relevant) {
                continue;
            }
            if (sb.length() > 0) {
                sb.append("; ");
            }
            sb.append(name).append('=').append(value);
            if ("__access_token".equals(name)) {
                hasAccessToken = true;
            }
        }

        // 没有 __access_token 就说明这份 cookie 已经不完整了
        return hasAccessToken ? sb.toString() : null;
    }

    private final HttpClient http = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .followRedirects(HttpClient.Redirect.NEVER)
            .build();

    /**
     * 查询 Cookie 状态。
     *
     * <p>会真的向 2ke 发一次请求验证会话是否还有效 —— 这比只看本地文件时间可靠。
     */
    @PreAuthorize("@ss.hasPermi('system:ops:view')")
    @GetMapping("/status")
    public AjaxResult status() {
        Map<String, Object> data = new LinkedHashMap<>();

        // ① 本地文件
        File f = new File(COOKIE_FILE);
        if (!f.exists()) {
            data.put("exists", false);
            data.put("healthy", false);
            data.put("message", "Cookie 文件不存在：" + COOKIE_FILE);
            return success(data);
        }
        data.put("exists", true);
        data.put("savedAt", FMT.format(
                LocalDateTime.ofInstant(Instant.ofEpochMilli(f.lastModified()), ZoneId.systemDefault())));

        // ② 读出 cookie
        String cookieHeader;
        int cookieCount = 0;
        try {
            JsonNode root = mapper.readTree(f);
            JsonNode arr = root.path("cookies");
            if (!arr.isArray() || arr.isEmpty()) {
                data.put("healthy", false);
                data.put("message", "Cookie 文件格式异常：没有 cookies 数组");
                return success(data);
            }
            cookieCount = arr.size();
            cookieHeader = buildCookieHeader(root);
        } catch (Exception e) {
            data.put("healthy", false);
            data.put("message", "Cookie 文件解析失败：" + e.getMessage());
            return success(data);
        }

        data.put("cookieCount", cookieCount);
        if (cookieHeader == null) {
            data.put("healthy", false);
            data.put("message", "Cookie 文件里缺少 __access_token（2ke 认证必需），请更新");
            return success(data);
        }

        // ③ 向 2ke 验证会话
        try {
            HttpRequest req = HttpRequest.newBuilder(URI.create(SESSION_URL))
                    .timeout(Duration.ofSeconds(15))
                    .header("User-Agent", UA)
                    .header("Accept", "application/json")
                    .header("Cookie", cookieHeader)
                    .GET()
                    .build();
            HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));

            if (resp.statusCode() != 200) {
                data.put("healthy", false);
                data.put("httpStatus", resp.statusCode());
                data.put("message", "会话校验失败：HTTP " + resp.statusCode() + "（多半是 Cookie 已过期）");
            } else {
                JsonNode j = mapper.readTree(resp.body());
                String expires = j.path("expires").asText(null);
                JsonNode user = j.path("user");

                if (expires == null || expires.isEmpty()) {
                    data.put("healthy", false);
                    data.put("message", "会话响应里没有 expires 字段");
                } else {
                    // ① Auth.js 的 30 天滚动窗口 —— 采集器每次访问都会自动续，不用管
                    Instant sessionExp = Instant.parse(expires);
                    data.put("sessionExpireAt",
                            FMT.format(LocalDateTime.ofInstant(sessionExp, ZoneId.systemDefault())));
                    data.put("sessionDaysLeft", Duration.between(Instant.now(), sessionExp).toDays());

                    // ② __access_token 的 JWT exp —— 这才是真正的硬到期
                    Object[] tokExp = parseAccessTokenExp(cookieHeader);
                    if (tokExp != null) {
                        String tokAt = (String) tokExp[0];
                        long tokDays = (Long) tokExp[1];
                        data.put("tokenExpireAt", tokAt);
                        data.put("tokenDaysLeft", tokDays);
                        data.put("expireAt", tokAt);        // 兼容：以真实到期为准
                        data.put("daysLeft", tokDays);
                        data.put("healthy", tokDays > 0);
                        if (tokDays <= 0) {
                            data.put("message", "凭据已过期，请更新 Cookie");
                        } else if (tokDays <= 30) {
                            data.put("message", "⚠️ 凭据只剩 " + tokDays + " 天，建议近期更新");
                        } else {
                            data.put("message", "正常（凭据还剩 " + tokDays + " 天）");
                        }
                    } else {
                        // 解析不出 exp 时退回会话窗口，并说明
                        long daysLeft = Duration.between(Instant.now(), sessionExp).toDays();
                        data.put("expireAt", data.get("sessionExpireAt"));
                        data.put("daysLeft", daysLeft);
                        data.put("healthy", daysLeft > 0);
                        data.put("message", "正常（无法解析凭据长期，按会话窗口显示）");
                    }
                }
                if (user.isObject()) {
                    data.put("sessionUser", user.path("name").asText(""));
                }
            }
        } catch (Exception e) {
            data.put("healthy", false);
            data.put("message", "会话校验异常：" + e.getClass().getSimpleName() + " - " + e.getMessage());
        }

        // ④ 采集器状态
        data.put("collectorActive", exec("systemctl", "is-active", COLLECTOR_UNIT).trim());
        return success(data);
    }

    /**
     * 更新 Cookie。
     *
     * <p>请求体：{@code {"cookie": "name1=value1; name2=value2; ..."}}
     *
     * <p>直接粘浏览器里那一整行 Cookie 最省事，后端会自动拆开、按名字决定归属域名、
     * 与现有文件合并（旧的 CAS cookie 保留，只替换 2ke 相关的）。
     *
     * <p>必须先验证新 cookie 真能通过 2ke 才落盘 —— 否则写进去一个坏值，
     * 采集器会一直 302，比更新前更糟。
     */
    @PreAuthorize("@ss.hasPermi('system:ops:restart')")
    @Log(title = "Cookie 续期", businessType = BusinessType.OTHER)
    @PostMapping("/update")
    public AjaxResult update(@RequestBody Map<String, Object> body) {
        Object rawObj = body.get("cookie");
        String raw = rawObj == null ? "" : String.valueOf(rawObj).trim();

        if (raw.isEmpty()) {
            return AjaxResult.error("Cookie 内容不能为空");
        }

        // 去掉可能粘进来的 "Cookie: " 前缀
        if (raw.regionMatches(true, 0, "cookie:", 0, 7)) {
            raw = raw.substring(7).trim();
        }
        // 去掉换行（浏览器复制常带）
        raw = raw.replace("\r", " ").replace("\n", " ").trim();

        // 拆成 name -> value
        Map<String, String> parsed = new LinkedHashMap<>();
        for (String part : raw.split(";")) {
            String seg = part.trim();
            if (seg.isEmpty()) continue;
            int eq = seg.indexOf('=');
            if (eq <= 0) continue;
            String name = seg.substring(0, eq).trim();
            String value = seg.substring(eq + 1).trim();
            if (name.isEmpty() || value.isEmpty()) continue;
            if (!name.matches("^[A-Za-z0-9_\\-\\.]+$")) continue;
            parsed.put(name, value);
        }

        if (parsed.isEmpty()) {
            return AjaxResult.error("没能从内容里解析出任何 cookie，请确认格式是 name=value; name=value");
        }
        if (!parsed.containsKey("__access_token")) {
            return AjaxResult.error("缺少 __access_token —— 这是 2ke 认证真正依赖的 cookie，"
                    + "请在 F12 → Network → 任一 2ke 请求 → Request Headers → Cookie 里完整复制");
        }

        // 用新 cookie 验证
        StringBuilder probe = new StringBuilder();
        for (Map.Entry<String, String> e : parsed.entrySet()) {
            if (probe.length() > 0) probe.append("; ");
            probe.append(e.getKey()).append('=').append(e.getValue());
        }
        String verifyMsg;
        try {
            HttpRequest req = HttpRequest.newBuilder(URI.create(SESSION_URL))
                    .timeout(Duration.ofSeconds(15))
                    .header("User-Agent", UA)
                    .header("Accept", "application/json")
                    .header("Cookie", probe.toString())
                    .GET()
                    .build();
            HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (resp.statusCode() != 200) {
                return AjaxResult.error("新 Cookie 验证失败：HTTP " + resp.statusCode()
                        + "（被 302 到登录页说明 cookie 无效），未写入");
            }
            JsonNode j = mapper.readTree(resp.body());
            String exp = j.path("expires").asText("");
            if (exp.isEmpty()) {
                return AjaxResult.error("新 Cookie 验证失败：会话响应没有 expires，未写入");
            }
            verifyMsg = "有效期至 " + FMT.format(
                    LocalDateTime.ofInstant(Instant.parse(exp), ZoneId.systemDefault()));
        } catch (Exception e) {
            return AjaxResult.error("新 Cookie 验证异常：" + e.getClass().getSimpleName()
                    + " - " + e.getMessage() + "，未写入");
        }

        // 备份
        try {
            Path old = Path.of(COOKIE_FILE);
            if (Files.exists(old)) {
                String stamp = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss"));
                Files.copy(old, Path.of("/root/2ke_cookie.json.bak-" + stamp),
                        StandardCopyOption.REPLACE_EXISTING);
            }
        } catch (Exception ignored) { }

        // 与旧文件合并：旧的 CAS cookie（SESSION/TGC 等）保留，同名的用新值覆盖
        List<Object> merged = new ArrayList<>();
        Set<String> used = new HashSet<>();
        try {
            Path p = Path.of(COOKIE_FILE);
            if (Files.exists(p)) {
                JsonNode oldRoot = mapper.readTree(p.toFile());
                for (JsonNode c : oldRoot.path("cookies")) {
                    String n = c.path("name").asText("");
                    if (n.isEmpty() || used.contains(n)) continue;
                    Map<String, Object> m = new LinkedHashMap<>();
                    m.put("name", n);
                    m.put("value", parsed.containsKey(n) ? parsed.get(n) : c.path("value").asText(""));
                    m.put("domain", c.path("domain").asText("2ke.jmu.edu.cn"));
                    m.put("path", c.path("path").asText("/"));
                    merged.add(m);
                    used.add(n);
                }
            }
        } catch (Exception ignored) { }

        // 新出现、旧文件里没有的 cookie，按名字猜域名
        for (Map.Entry<String, String> e : parsed.entrySet()) {
            if (used.contains(e.getKey())) continue;
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("name", e.getKey());
            m.put("value", e.getValue());
            m.put("domain", guessDomain(e.getKey()));
            m.put("path", "/");
            merged.add(m);
            used.add(e.getKey());
        }

        try {
            Map<String, Object> root = new LinkedHashMap<>();
            root.put("cookies", merged);
            root.put("saved_at", Instant.now().toString());

            Path p = Path.of(COOKIE_FILE);
            Files.writeString(p, mapper.writeValueAsString(root), StandardCharsets.UTF_8);
            try {
                Files.setPosixFilePermissions(p, PosixFilePermissions.fromString("rw-------"));
            } catch (UnsupportedOperationException ignored) { }
        } catch (IOException e) {
            return AjaxResult.error("写入 Cookie 文件失败：" + e.getMessage());
        }

        // 重启采集器
        exec("systemctl", "restart", COLLECTOR_UNIT);
        try {
            Thread.sleep(12000);
        } catch (InterruptedException ignored) { }

        String active = exec("systemctl", "is-active", COLLECTOR_UNIT).trim();
        String recentLog = exec("journalctl", "-u", COLLECTOR_UNIT, "-n", "3", "--no-pager");

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("verify", verifyMsg);
        data.put("cookieCount", merged.size());
        data.put("collectorActive", active);
        data.put("recentLog", recentLog.trim());

        boolean ok = "active".equals(active) && recentLog.contains(" ok ");
        if (ok) {
            return AjaxResult.success("Cookie 已更新（" + verifyMsg + "），采集器运行正常", data);
        }
        return AjaxResult.error("Cookie 已写入，但采集器未见成功日志（" + active + "），请查看下方日志", data);
    }

    /**
     * 从 __access_token 这个 JWT 里取出真正的到期时间。
     *
     * <p>为什么需要它：{@code /api/auth/session} 返回的 expires 是 Auth.js 的
     * 30 天滚动窗口，每次访问都会往后推 —— 拿它当"到期时间"会让人误以为
     * 一个月后就要手工续期。真正决定 2ke 放不放行的是 __access_token，
     * 它是 .jmu.edu.cn 父域上的 JWT，exp 一般在一年后。
     *
     * @return [到期时间文本, 剩余天数]；解析失败返回 null
     */
    private Object[] parseAccessTokenExp(String cookieHeader) {
        if (cookieHeader == null) {
            return null;
        }
        String token = null;
        for (String seg : cookieHeader.split(";")) {
            String t = seg.trim();
            if (t.startsWith("__access_token=")) {
                token = t.substring("__access_token=".length()).trim();
                break;
            }
        }
        if (token == null || token.isEmpty()) {
            return null;
        }
        try {
            String[] parts = token.split("\\.");
            if (parts.length < 2) {
                return null;
            }
            String p2 = parts[1];
            // JWT 的 Base64URL 段可能缺 padding
            int pad = (4 - p2.length() % 4) % 4;
            if (pad > 0) {
                p2 = p2 + "=".repeat(pad);
            }
            byte[] raw = java.util.Base64.getUrlDecoder().decode(p2);
            JsonNode node = mapper.readTree(new String(raw, StandardCharsets.UTF_8));
            long exp = node.path("exp").asLong(0);
            if (exp <= 0) {
                return null;
            }
            Instant inst = Instant.ofEpochSecond(exp);
            long days = Duration.between(Instant.now(), inst).toDays();
            return new Object[]{FMT.format(LocalDateTime.ofInstant(inst, ZoneId.systemDefault())), days};
        } catch (Exception e) {
            return null;
        }
    }

    /** 按 cookie 名字推断归属域名 */
    private String guessDomain(String name) {
        if ("__access_token".equals(name)) {
            return ".jmu.edu.cn";
        }
        if (name.startsWith("__Secure-") || name.startsWith("__Host-")) {
            return "2ke.jmu.edu.cn";
        }
        return "2ke.jmu.edu.cn";
    }

    /** 执行命令，带超时；失败返回空串 */
    private String exec(String... cmd) {
        ProcessBuilder pb = new ProcessBuilder(cmd);
        pb.redirectErrorStream(true);
        Process p = null;
        try {
            p = pb.start();
            StringBuilder sb = new StringBuilder();
            try (java.io.BufferedReader br = new java.io.BufferedReader(
                    new java.io.InputStreamReader(p.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = br.readLine()) != null) {
                    sb.append(line).append('\n');
                    if (sb.length() > 64 * 1024) break;
                }
            }
            if (!p.waitFor(10, java.util.concurrent.TimeUnit.SECONDS)) {
                p.destroyForcibly();
            }
            return sb.toString();
        } catch (Exception e) {
            return "";
        } finally {
            if (p != null && p.isAlive()) {
                p.destroyForcibly();
            }
        }
    }
}
