package com.ruoyi.system.controller;

import com.ruoyi.common.annotation.Log;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.page.TableDataInfo;
import com.ruoyi.common.enums.BusinessType;
import com.ruoyi.system.domain.TLecture;
import com.ruoyi.system.mapper.TLectureMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * 讲座管理 —— 集大教务（jwxt）的讲座列表，只读展示 + 手动触发采集 + 更新登录态。
 *
 * <p>数据链路：/opt/jwxt/collector_jwxt.py（cron 每 30 分钟）
 * → GET /student/for-std/lecture-enroll/un-enroll-search → 写 ry-2ke.t_lecture。
 *
 * <p>本控制器不改业务数据（讲座由教务系统产生），只做：
 * <ul>
 *   <li>列表/筛选/统计</li>
 *   <li>「立即采集」——执行固定脚本，不接受任何参数（避免命令注入）</li>
 *   <li>「更新登录态」——把前端贴的 Cookie 行写进 /opt/jwxt/cookie.txt</li>
 * </ul>
 */
@RestController
@RequestMapping("/system/lecture")
public class TLectureController extends BaseController {

    private static final String COOKIE_FILE = "/opt/jwxt/cookie.txt";
    private static final String TGC_FILE = "/opt/jwxt/tgc.txt";
    private static final String PUSH_CONF = "/opt/jwxt/push.json";
    private static final String STATE_FILE = "/opt/jwxt/state.json";
    private static final String COLLECTOR = "/opt/jwxt/collector_jwxt.py";

    @Autowired
    private TLectureMapper lectureMapper;

    /** 列表（分页） */
    @PreAuthorize("@ss.hasPermi('system:lecture:list')")
    @GetMapping("/list")
    public TableDataInfo list(TLecture q) {
        startPage();
        List<TLecture> list = lectureMapper.selectLectureList(q);
        return getDataTable(list);
    }

    /** 类型下拉 + 统计 + 采集器状态 */
    @PreAuthorize("@ss.hasPermi('system:lecture:list')")
    @GetMapping("/status")
    public AjaxResult status() {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("types", lectureMapper.selectTypeOptions());
        data.put("stat", lectureMapper.selectLectureStat());

        // 采集器状态
        Map<String, Object> coll = new LinkedHashMap<>();
        File cookie = new File(COOKIE_FILE);
        coll.put("cookieExists", cookie.exists());
        coll.put("cookieBytes", cookie.exists() ? cookie.length() : 0);
        coll.put("cookieTime", cookie.exists()
                ? new java.text.SimpleDateFormat("yyyy-MM-dd HH:mm").format(new java.util.Date(cookie.lastModified())) : null);
        String collectorState = null;
        try {
            collectorState = new String(Files.readAllBytes(Paths.get(STATE_FILE)), StandardCharsets.UTF_8);
        } catch (Exception ignored) {
        }
        coll.put("state", collectorState);
        data.put("collector", coll);
        return AjaxResult.success(data);
    }

    /** 立即采集（执行固定脚本，无参数） */
    @PreAuthorize("@ss.hasPermi('system:lecture:collect')")
    @Log(title = "讲座管理", businessType = BusinessType.OTHER)
    @PostMapping("/collect")
    public AjaxResult collect() {
        File f = new File(COLLECTOR);
        if (!f.exists()) {
            return AjaxResult.error("采集脚本不存在：" + COLLECTOR);
        }
        try {
            ProcessBuilder pb = new ProcessBuilder("/usr/bin/python3", COLLECTOR, "--verbose");
            pb.directory(new File("/opt/jwxt"));
            pb.redirectErrorStream(true);
            Process p = pb.start();
            StringBuilder out = new StringBuilder();
            try (java.io.BufferedReader br = new java.io.BufferedReader(
                    new java.io.InputStreamReader(p.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                int n = 0;
                while ((line = br.readLine()) != null && n++ < 200) {
                    out.append(line).append('\n');
                }
            }
            boolean done = p.waitFor(90, TimeUnit.SECONDS);
            int code = done ? p.exitValue() : -1;
            Map<String, Object> data = new LinkedHashMap<>();
            data.put("exitCode", code);
            data.put("log", out.toString());
            if (code == 0) {
                lectureMapper.closeExpired();
                return AjaxResult.success("采集完成", data);
            }
            return AjaxResult.error("采集未成功（exit=" + code + "），看日志", data);
        } catch (Exception e) {
            return AjaxResult.error("执行采集失败：" + e.getMessage());
        }
    }

    /** 推送开关：读 */
    @PreAuthorize("@ss.hasPermi('system:lecture:list')")
    @GetMapping("/push-config")
    public AjaxResult getPushConfig() {
        Map<String, Object> data = new LinkedHashMap<>();
        boolean enabled = false;
        try {
            String s = new String(Files.readAllBytes(Paths.get(PUSH_CONF)), StandardCharsets.UTF_8);
            enabled = s.replace(" ", "").contains("\"enabled\":true");
            data.put("raw", s);
        } catch (Exception ignored) {
        }
        data.put("enabled", enabled);
        data.put("delivery", lectureMapper.selectDeliveryStat());
        return AjaxResult.success(data);
    }

    /** 推送开关：写 */
    @PreAuthorize("@ss.hasPermi('system:lecture:collect')")
    @Log(title = "讲座管理", businessType = BusinessType.UPDATE)
    @PostMapping("/push-config")
    public AjaxResult setPushConfig(@RequestBody Map<String, Object> body) {
        boolean on = Boolean.TRUE.equals(body.get("enabled"))
                || "true".equalsIgnoreCase(String.valueOf(body.get("enabled")));
        try {
            String json = "{\n \"enabled\": " + on + ",\n"
                    + " \"note\": \"enabled=false 只采集不推送；baseline_done 由采集器维护\"\n}\n";
            Path p = Paths.get(PUSH_CONF);
            Files.write(p, json.getBytes(StandardCharsets.UTF_8));
            chmod600(p);
            return AjaxResult.success(on
                    ? "讲座推送已开启：以后有新讲座会推给订阅者"
                    : "讲座推送已关闭：只采集，不打扰学生");
        } catch (Exception e) {
            return AjaxResult.error("写入失败：" + e.getMessage());
        }
    }

    /** 推送记录（分页） */
    @PreAuthorize("@ss.hasPermi('system:lecture:delivery')")
    @GetMapping("/delivery/list")
    public TableDataInfo deliveryList(@RequestParam Map<String, Object> q) {
        startPage();
        List<Map<String, Object>> list = lectureMapper.selectDeliveryList(q);
        return getDataTable(list);
    }

    /** 推送记录状态统计（给页面顶部标签用） */
    @PreAuthorize("@ss.hasPermi('system:lecture:delivery')")
    @GetMapping("/delivery/stat")
    public AjaxResult deliveryStat() {
        return AjaxResult.success(lectureMapper.selectDeliveryStat());
    }

    /**
     * 更新登录态。支持两种输入：
     * <ul>
     *   <li><b>TGC（推荐）</b>——从 cas.paas.jmu.edu.cn 拿到的 TGC，采集器会用它自动换 jwxt 会话，
     *       只要 TGC 有效就永不需要人工干预</li>
     *   <li><b>完整 Cookie 行</b>——含 __pstsid__ 和 SESSION（旧方式，2 天就得换一次）</li>
     * </ul>
     */
    @PreAuthorize("@ss.hasPermi('system:lecture:collect')")
    @Log(title = "讲座管理", businessType = BusinessType.UPDATE)
    @PostMapping("/cookie")
    public AjaxResult updateCookie(@RequestBody Map<String, Object> body) {
        String rawVal = body.get("cookie") == null ? "" : String.valueOf(body.get("cookie"));
        String c = rawVal.replace("\r", " ").replace("\n", " ").trim();
        if (c.regionMatches(true, 0, "cookie:", 0, 7)) {
            c = c.substring(7).trim();
        }
        c = c.replaceAll("\\s+", " ");

        if (c.isEmpty()) {
            return AjaxResult.error("内容为空");
        }

        boolean looksLikeTgc = c.matches("(?i)^(TGC=)?[A-Za-z0-9._\\-+/=]{20,}$");
        boolean looksLikeCookie = c.contains("__pstsid__") && c.contains("SESSION");

        try {
            if (looksLikeTgc && !looksLikeCookie) {
                String v = c.replaceFirst("(?i)^TGC=", "");
                Path p = Paths.get(TGC_FILE);
                Files.write(p, v.getBytes(StandardCharsets.UTF_8));
                chmod600(p);
                return AjaxResult.success("TGC 已保存（" + v.length() + " 字符）。点「立即采集」验证；"
                        + "只要 TGC 有效，之后全自动，不用再管");
            }
            if (looksLikeCookie) {
                Path p = Paths.get(COOKIE_FILE);
                Files.write(p, (c + "\n").getBytes(StandardCharsets.UTF_8));
                chmod600(p);
                return AjaxResult.success("Cookie 已保存（" + c.length() + " 字符）。"
                        + "注意这是临时方案，2 天会过期；贴 TGC 可以免维护");
            }
            return AjaxResult.error("认不出来。要么贴 TGC 的值，要么贴含 __pstsid__ 和 SESSION 的整行 Cookie");
        } catch (Exception e) {
            return AjaxResult.error("写入失败：" + e.getMessage());
        }
    }

    private void chmod600(Path p) {
        try {
            Files.setPosixFilePermissions(p,
                    java.nio.file.attribute.PosixFilePermissions.fromString("rw-------"));
        } catch (Exception ignored) {
        }
    }
}
