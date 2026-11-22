package com.ruoyi.system.controller;

import com.ruoyi.common.annotation.Log;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.enums.BusinessType;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 二维码管理 —— 订阅页两个二维码的状态与更换。
 *
 * <p>业务背景：
 * <ul>
 *   <li>「加入企业」码（join.png）内容是一条长期邀请链接，不会过期，不需要更换</li>
 *   <li>「微信插件」码（plugin.png）企业微信侧 7 天过期，且**没有接口能生成**
 *       （实测 corp/get_join_qrcode → 48002 权限不足；插件相关接口全部 404），
 *       只能由管理员在企业微信 App 里「重新获取」后截图上传</li>
 * </ul>
 *
 * <p>实现说明：图片解码校验、裁剪成 600×600、原子替换由本机 127.0.0.1:18091 的服务完成
 * （复用已验证的实现，避免在 Java 里重写图像处理）。本控制器只做鉴权、状态汇总和转发。
 */
@RestController
@RequestMapping("/system/qrcode")
public class QRCodeController extends BaseController {

    private static final String WEB = "/var/www/2ke-subscribe";
    private static final String PLUGIN = WEB + "/plugin.png";
    private static final String JOIN = WEB + "/join.png";
    private static final String EXPIRY = WEB + "/.plugin-expiry";
    private static final String TOKEN_FILE = "/root/qrbot/upload-token";
    private static final String UPLOAD_BASE = "http://127.0.0.1:18091/";

    private static String readToken() {
        try {
            String t = new String(Files.readAllBytes(Paths.get(TOKEN_FILE)), StandardCharsets.UTF_8).trim();
            return t.isEmpty() ? null : t;
        } catch (Exception e) {
            return null;
        }
    }

    private static String readText(String path) {
        try {
            return new String(Files.readAllBytes(Paths.get(path)), StandardCharsets.UTF_8).trim();
        } catch (Exception e) {
            return null;
        }
    }

    private static String fmt(long ms) {
        return LocalDateTime.ofInstant(java.time.Instant.ofEpochMilli(ms), java.time.ZoneId.systemDefault())
                .format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm"));
    }

    /** 二维码状态：右码到期日、剩余天数、图片时间与版本号（前端用来破缓存） */
    @PreAuthorize("@ss.hasPermi('system:qrcode:list')")
    @GetMapping("/status")
    public AjaxResult status() {
        Map<String, Object> m = new LinkedHashMap<>();
        File plugin = new File(PLUGIN);
        m.put("pluginExists", plugin.exists());
        m.put("pluginBytes", plugin.exists() ? plugin.length() : 0L);
        m.put("pluginTime", plugin.exists() ? fmt(plugin.lastModified()) : null);
        m.put("pluginVersion", plugin.exists() ? plugin.lastModified() : 0L);

        String exp = readText(EXPIRY);
        m.put("expiry", exp);
        Long days = null;
        try {
            if (exp != null && exp.matches("\\d{4}-\\d{2}-\\d{2}")) {
                days = ChronoUnit.DAYS.between(LocalDate.now(), LocalDate.parse(exp));
            }
        } catch (Exception ignored) {
        }
        m.put("daysLeft", days);
        m.put("expired", days != null && days < 0);

        File join = new File(JOIN);
        m.put("joinExists", join.exists());
        m.put("joinBytes", join.exists() ? join.length() : 0L);
        m.put("joinVersion", join.exists() ? join.lastModified() : 0L);

        m.put("uploadReady", readToken() != null && new File(WEB).canWrite());
        return AjaxResult.success(m);
    }

    /**
     * 上传新的「微信插件」码截图。
     * 请求体原样转发给本机图像服务：{"data":"data:image/png;base64,..."}
     */
    @PreAuthorize("@ss.hasPermi('system:qrcode:upload')")
    @Log(title = "二维码管理", businessType = BusinessType.UPDATE)
    @PostMapping("/upload")
    public AjaxResult upload(@RequestBody String rawBody) {
        String token = readToken();
        if (token == null) {
            return AjaxResult.error("本地图像服务未初始化（缺 /root/qrbot/upload-token），请联系运维");
        }
        if (rawBody == null || rawBody.length() < 100) {
            return AjaxResult.error("请求内容为空");
        }
        if (rawBody.length() > 16 * 1024 * 1024) {
            return AjaxResult.error("图片过大，请压缩后再传（上限约 12MB）");
        }
        HttpURLConnection conn = null;
        try {
            URL u = new URL(UPLOAD_BASE + token);
            conn = (HttpURLConnection) u.openConnection();
            conn.setRequestMethod("POST");
            conn.setDoOutput(true);
            conn.setConnectTimeout(5000);
            conn.setReadTimeout(120000);
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            byte[] body = rawBody.getBytes(StandardCharsets.UTF_8);
            conn.setFixedLengthStreamingMode(body.length);
            try (OutputStream os = conn.getOutputStream()) {
                os.write(body);
            }
            int code = conn.getResponseCode();
            InputStream is = (code >= 400) ? conn.getErrorStream() : conn.getInputStream();
            String resp = readAll(is);
            if (code >= 400) {
                return AjaxResult.error("图像服务返回 " + code + "：" + resp);
            }
            boolean ok = resp != null && (resp.contains("\"ok\": true") || resp.contains("\"ok\":true"));
            if (ok) {
                return AjaxResult.success("二维码已更新", resp);
            }
            return AjaxResult.error(resp == null ? "更新失败（无返回）" : resp);
        } catch (Exception e) {
            return AjaxResult.error("调用本地图像服务失败：" + e.getMessage());
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    private static String readAll(InputStream is) {
        if (is == null) {
            return null;
        }
        try (InputStream in = is; ByteArrayOutputStream bos = new ByteArrayOutputStream()) {
            byte[] buf = new byte[4096];
            int n;
            while ((n = in.read(buf)) > 0) {
                bos.write(buf, 0, n);
            }
            return new String(bos.toByteArray(), StandardCharsets.UTF_8);
        } catch (Exception e) {
            return null;
        }
    }
}
