package com.ruoyi.system.controller;

import com.ruoyi.common.annotation.Log;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.enums.BusinessType;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.TimeUnit;

/**
 * 系统运维 —— 服务状态 / 日志查看 / 重启。
 *
 * <p>设计约束：
 * <ul>
 *   <li>只允许操作白名单里的 systemd unit，unit 名不接受前端传入，避免命令注入</li>
 *   <li>只提供「重启」，不提供「停止」—— 手动 stop 后 systemd 的 Restart=always 不会拉起，
 *       容易把系统点哑</li>
 *   <li>日志按关键词归类成 INFO/WARN/ERROR，不修改各服务自身的输出格式</li>
 * </ul>
 */
@RestController
@RequestMapping("/system/ops")
public class ServiceOpsController extends BaseController {

    /** key -> {unit, 显示名, 操作方式} */
    private static final Map<String, String[]> SERVICES = new LinkedHashMap<>();
    static {
        SERVICES.put("collector",  new String[]{"2ke-hub-mysql",   "采集器",   "restart"});
        SERVICES.put("dispatcher", new String[]{"2ke-dispatcher",  "推送器",   "restart"});
        SERVICES.put("wecom",      new String[]{"2ke-wecom",       "回调服务", "restart"});
        SERVICES.put("lecture",    new String[]{"jwxt-collector.timer", "讲座采集", "restart"});
        SERVICES.put("backend",    new String[]{"ruoyi-app",       "若依后端", "restart"});
        SERVICES.put("nginx",      new String[]{"nginx",           "Nginx",    "reload"});
        SERVICES.put("mysql",      new String[]{"ruoyi-mysql",     "MySQL",    "restart"});
        SERVICES.put("redis",      new String[]{"ruoyi-redis",     "Redis",    "restart"});
    }

    /** 服务状态总览 */
    @PreAuthorize("@ss.hasPermi('system:ops:view')")
    @GetMapping("/services")
    public AjaxResult services() {
        List<Map<String, Object>> list = new ArrayList<>();
        for (Map.Entry<String, String[]> e : SERVICES.entrySet()) {
            String key = e.getKey();
            String unit = e.getValue()[0];
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("key", key);
            m.put("unit", unit);
            m.put("name", e.getValue()[1]);
            m.put("action", e.getValue()[2]);
            m.put("active", exec("systemctl", "is-active", unit).trim());
            m.put("enabled", exec("systemctl", "is-enabled", unit).trim());
            String since = exec("systemctl", "show", unit, "-p", "ActiveEnterTimestamp", "--value").trim();
            m.put("since", since);
            m.put("uptime", humanUptime(since));
            list.add(m);
        }
        return success(list);
    }

    /**
     * 某个服务的日志。
     *
     * @param key   服务 key（白名单内）
     * @param lines 行数，1~1000
     * @param level 过滤级别：ALL / INFO / WARN / ERROR
     */
    @PreAuthorize("@ss.hasPermi('system:ops:view')")
    @GetMapping("/logs")
    public AjaxResult logs(@RequestParam String key,
                           @RequestParam(defaultValue = "200") int lines,
                           @RequestParam(defaultValue = "ALL") String level,
                           @RequestParam(defaultValue = "1h") String since) {
        String[] svc = SERVICES.get(key);
        if (svc == null) {
            return AjaxResult.error("未知服务：" + key);
        }
        int n = Math.max(1, Math.min(lines, 1000));

        // 时间窗口：默认只看最近 1 小时，避免几小时前的启动失败糊满屏幕
        String sinceArg = switch (since == null ? "1h" : since) {
            case "6h" -> "6 hours ago";
            case "24h" -> "24 hours ago";
            case "all" -> null;
            default -> "1 hour ago";
        };

        // -r = 倒序输出，最新的在第一行
        String raw = (sinceArg == null)
                ? exec("journalctl", "-u", svc[0], "-n", String.valueOf(n),
                       "--no-pager", "-o", "short-iso", "-r")
                : exec("journalctl", "-u", svc[0], "--since", sinceArg, "-n", String.valueOf(n),
                       "--no-pager", "-o", "short-iso", "-r");

        List<Map<String, Object>> rows = new ArrayList<>();
        int cntErr = 0, cntWarn = 0;
        for (String line : raw.split("\n")) {
            if (line == null || line.trim().isEmpty()) continue;
            // journalctl 在没日志时会输出 "-- No entries --"，那是提示语不是日志行。
            // 不过滤的话前端会把它渲染成一条 INFO 记录，用户看到莫名其妙的一句英文。
            String t = line.trim();
            if (t.equals("-- No entries --") || t.equals("-- No entries --.")) continue;
            String lv = levelOf(line);
            if ("ERROR".equals(lv)) cntErr++;
            else if ("WARN".equals(lv)) cntWarn++;
            if (!"ALL".equalsIgnoreCase(level) && !lv.equalsIgnoreCase(level)) continue;

            Map<String, Object> m = new LinkedHashMap<>();
            // journalctl short-iso 格式：2026-10-21T22:08:34+08:00 host unit[pid]: msg
            String ts = "";
            String msg = line;
            int sp = line.indexOf(' ');
            if (sp > 0 && line.startsWith("20")) {
                ts = line.substring(0, sp);
                msg = line.substring(sp + 1);
                int colon = msg.indexOf("]: ");
                if (colon > 0) msg = msg.substring(colon + 3);
            }
            m.put("ts", ts);
            m.put("level", lv);
            m.put("msg", msg);
            rows.add(m);
        }

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("unit", svc[0]);
        data.put("name", svc[1]);
        data.put("since", since);
        data.put("total", rows.size());
        data.put("errorCount", cntErr);
        data.put("warnCount", cntWarn);
        data.put("rows", rows);
        return success(data);
    }

    /** 重启/重载某个服务 */
    @PreAuthorize("@ss.hasPermi('system:ops:restart')")
    @Log(title = "服务运维", businessType = BusinessType.OTHER)
    @PostMapping("/restart")
    public AjaxResult restart(@RequestParam String key) {
        String[] svc = SERVICES.get(key);
        if (svc == null) {
            return AjaxResult.error("未知服务：" + key);
        }
        String unit = svc[0];
        String action = svc[2];

        // 重启若依自己会中断当前请求，用 systemd-run 延迟 3 秒执行
        if ("ruoyi-app".equals(unit)) {
            exec("systemd-run", "--on-active=3", "systemctl", "restart", unit);
            return AjaxResult.success("已排队，3 秒后重启后端（本页会短暂失联，稍后刷新）");
        }
        if ("reload".equals(action)) {
            String out = exec("systemctl", "reload", unit);
            return AjaxResult.success("已重载 " + svc[1] + (out.isEmpty() ? "" : "：" + out.trim()));
        }
        exec("systemctl", "restart", unit);
        // 等待一小会儿再看状态
        try { Thread.sleep(1500); } catch (InterruptedException ignored) { }
        String st = exec("systemctl", "is-active", unit).trim();
        if ("active".equals(st)) {
            return AjaxResult.success(svc[1] + " 已重启");
        }
        return AjaxResult.error(svc[1] + " 重启后状态为 " + st + "，请查看日志");
    }

    /** 日志级别归类（不改各服务输出格式，按关键词推断） */
    private String levelOf(String line) {
        String l = line.toLowerCase();

        // 例外：「发送 0，跳过 12，失败 0」这类汇总结论是正常的，
        // 只因含「失败」二字会被误判成 ERROR，这里先排除掉。
        if (l.contains("失败 0") || l.contains("失败0")
                || l.matches(".*失败\\s*[:：]\\s*0.*")
                || l.contains("failed 0") || l.contains("fail 0")
                || l.contains("failed=0") || l.contains("error 0")) {
            return "INFO";
        }

        if (l.contains("fail") || l.contains("error") || l.contains("!!")
                || l.contains("失败") || l.contains("exception") || l.contains("traceback")
                // Python traceback 的续行，单独看都是普通文本，必须一起归为 ERROR
                || l.contains("raise ") || l.contains("file \"")
                || l.contains(".py\", line") || l.contains("during handling of the above")
                || l.trim().startsWith("c = ") || l.contains("errno ")) {
            return "ERROR";
        }
        if (l.contains("warn") || l.contains("⚠") || l.contains("告警")
                || l.contains("重试") || l.contains("异常")) {
            return "WARN";
        }
        return "INFO";
    }

    /** 单个命令最多读这么多输出，防止 journalctl 输出异常巨大时占满内存 */
    private static final int MAX_OUTPUT = 512 * 1024;

    /**
     * 执行命令，带超时；失败返回空串而不抛异常，保证面板总能渲染。
     *
     * <p>读输出必须放在独立线程：BufferedReader.readLine() 在子进程
     * 「既不输出也不退出」时会永久阻塞，如果直接在主线程里读，
     * 下面的 waitFor(10s) 根本执行不到，Tomcat 工作线程会被拖死。
     * 几个这样的请求就能让整个后台无响应。
     */
    private String exec(String... cmd) {
        ProcessBuilder pb = new ProcessBuilder(cmd);
        pb.redirectErrorStream(true);
        Process p = null;
        try {
            p = pb.start();
            final Process proc = p;
            final StringBuilder sb = new StringBuilder();

            Thread reader = new Thread(() -> {
                try (BufferedReader br = new BufferedReader(
                        new InputStreamReader(proc.getInputStream(), StandardCharsets.UTF_8))) {
                    String line;
                    while ((line = br.readLine()) != null) {
                        synchronized (sb) {
                            sb.append(line).append('\n');
                            if (sb.length() > MAX_OUTPUT) {
                                break;
                            }
                        }
                    }
                } catch (Exception ignored) {
                    // 子进程被 destroyForcibly 时这里会抛，忽略即可
                }
            });
            reader.setDaemon(true);
            reader.start();

            if (!p.waitFor(10, TimeUnit.SECONDS)) {
                p.destroyForcibly();
                p.waitFor(2, TimeUnit.SECONDS);
            }
            reader.join(2000);

            synchronized (sb) {
                return sb.toString();
            }
        } catch (Exception e) {
            return "";
        } finally {
            if (p != null && p.isAlive()) {
                p.destroyForcibly();
            }
        }
    }

    /** 把 ActiveEnterTimestamp 转成"x 分钟前" */
    private String humanUptime(String since) {
        if (since == null || since.trim().isEmpty()) return "-";
        try {
            java.util.Date d = new java.text.SimpleDateFormat("EEE yyyy-MM-dd HH:mm:ss zzz", Locale.US)
                    .parse(since.trim());
            long min = (System.currentTimeMillis() - d.getTime()) / 60000L;
            if (min < 1) return "刚刚";
            if (min < 60) return min + " 分钟前";
            long hour = min / 60;
            if (hour < 24) return hour + " 小时前";
            return (hour / 24) + " 天前";
        } catch (Exception e) {
            return since.trim();
        }
    }
}
