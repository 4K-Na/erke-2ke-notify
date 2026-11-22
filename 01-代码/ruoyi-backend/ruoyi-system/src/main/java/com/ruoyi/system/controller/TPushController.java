package com.ruoyi.system.controller;

import com.ruoyi.common.annotation.Log;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.enums.BusinessType;
import com.ruoyi.system.domain.TSubscriber;
import com.ruoyi.system.mapper.TSubscriberMapper;
import com.ruoyi.system.service.WeComService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.nio.charset.StandardCharsets;
import java.util.*;

/**
 * 手动推送 —— 临时系统通知 / 故障提醒 / 自定义消息。
 *
 * 与自动推送（Dispatcher）分开：这里发的消息不依赖 2ke 有没有新活动，
 * 随时可以给「自己 / 全体 / 指定订阅者」发一条。
 *
 * 注意：手动消息不写入 t_delivery —— 那张表是「活动→订阅者」的投递矩阵，
 * 塞进去会污染首页「已推送」统计口径。操作留痕走 RuoYi 的 @Log。
 */
@RestController
@RequestMapping("/system/push")
public class TPushController extends BaseController {

    /** 手动推送用的图片存放目录（挂在订阅站根下，学生可直接点开看） */
    private static final String PUSH_IMG_DIR = "/var/www/2ke-subscribe/push";
    private static final String PUSH_IMG_BASE = "https://example.com/push/";
    private static final long PUSH_IMG_MAX = 12L * 1024 * 1024;

    @Autowired
    private WeComService weComService;

    @Autowired
    private TSubscriberMapper subscriberMapper;

    /** 可选的接收对象列表（给前端下拉用） */
    @PreAuthorize("@ss.hasPermi('system:push:send')")
    @GetMapping("/targets")
    public AjaxResult targets() {
        TSubscriber q = new TSubscriber();
        q.setChannel("wecom");
        q.setStatus("0");
        List<TSubscriber> list = subscriberMapper.selectTSubscriberList(q);
        List<Map<String, Object>> out = new ArrayList<>();
        for (TSubscriber s : list) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("subscriberId", s.getSubscriberId());
            m.put("externalId", s.getExternalId());
            m.put("name", s.getNickname() != null ? s.getNickname() : s.getRealName());
            m.put("className", s.getClassName());
            out.add(m);
        }
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("subscribers", out);
        data.put("adminUserid", weComService.getAdminUserid());
        return success(data);
    }

    /**
     * 发送自定义消息。
     *
     * body:
     *   scope   : self | all | ids
     *   userIds : 当 scope=ids 时，企业微信 userid 列表
     *   title   : 可选，会作为正文首行
     *   content : 正文
     */
    @PreAuthorize("@ss.hasPermi('system:push:send')")
    @Log(title = "手动推送", businessType = BusinessType.OTHER)
    @PostMapping("/send")
    public AjaxResult send(@RequestBody Map<String, Object> body) {
        String scope = str(body.get("scope"), "self");
        String title = str(body.get("title"), "");
        String content = str(body.get("content"), "");

        if (content.trim().isEmpty()) {
            return AjaxResult.error("消息内容不能为空");
        }
        // 企业微信 text 消息硬上限 2048 字节（中文 3 字节/字，约 680 字）
        int headBytes = title.trim().isEmpty() ? 0
                : ("【" + title.trim() + "】\n\n").getBytes(StandardCharsets.UTF_8).length;
        int bodyBytes = content.trim().getBytes(StandardCharsets.UTF_8).length;
        if (headBytes + bodyBytes > 2048) {
            return AjaxResult.error("消息过长：" + (headBytes + bodyBytes)
                    + " 字节，企业微信上限 2048 字节（中文约 680 字），请精简后再发");
        }

        String touser;
        if ("all".equals(scope)) {
            touser = "@all";
        } else if ("ids".equals(scope)) {
            Object raw = body.get("userIds");
            if (!(raw instanceof List) || ((List<?>) raw).isEmpty()) {
                return AjaxResult.error("请选择至少一个接收人");
            }
            List<String> ids = new ArrayList<>();
            for (Object o : (List<?>) raw) {
                String s = String.valueOf(o).trim();
                // 过滤 @all 之类的保留字，避免绕过 scope 直接群发；也挡掉空串
                if (!s.isEmpty() && !s.startsWith("@")) ids.add(s);
            }
            if (ids.isEmpty()) {
                return AjaxResult.error("接收人无效");
            }
            touser = String.join("|", ids);
        } else {
            String admin = weComService.getAdminUserid();
            if (admin == null || admin.isEmpty()) {
                return AjaxResult.error("未配置 admin_userid，无法发给自己");
            }
            touser = admin;
        }

        StringBuilder sb = new StringBuilder();
        if (!title.trim().isEmpty()) {
            sb.append("【").append(title.trim()).append("】\n\n");
        }
        sb.append(content.trim());

        // ① 先发文字
        Map<String, Object> textRes = weComService.sendText(touser, sb.toString());
        boolean textOk = Boolean.TRUE.equals(textRes.get("ok"));

        // ② 如果有图片，再单独发一条 image（企业微信一条消息只能一个 msgtype）
        String imgB64 = str(body.get("imageBase64"), "");
        Map<String, Object> imgRes = null;
        if (!imgB64.isEmpty()) {
            try {
                java.util.regex.Matcher m = java.util.regex.Pattern
                        .compile("^data:image/([A-Za-z]+);base64,(.+)$", java.util.regex.Pattern.DOTALL)
                        .matcher(imgB64);
                if (!m.matches()) {
                    imgRes = new LinkedHashMap<>();
                    imgRes.put("ok", false);
                    imgRes.put("errmsg", "图片数据格式不对");
                } else {
                    byte[] raw = java.util.Base64.getDecoder().decode(m.group(2));
                    if (raw.length > 10L * 1024 * 1024) {
                        imgRes = new LinkedHashMap<>();
                        imgRes.put("ok", false);
                        imgRes.put("errmsg", "图片超过 10MB（企业微信图片上限）");
                    } else {
                        String mediaId = weComService.uploadImage(raw);
                        imgRes = weComService.sendImage(touser, mediaId);
                    }
                }
            } catch (Exception e) {
                imgRes = new LinkedHashMap<>();
                imgRes.put("ok", false);
                imgRes.put("errmsg", "图片发送异常：" + e.getMessage());
            }
        }

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("text", textRes);
        if (imgRes != null) {
            data.put("image", imgRes);
        }
        data.put("withImage", imgRes != null);

        boolean imgOk = imgRes == null || Boolean.TRUE.equals(imgRes.get("ok"));
        String where = ("@all".equals(touser) ? "全体成员" : touser);

        if (textOk && imgOk) {
            return AjaxResult.success(
                    imgRes == null ? ("已发送到 " + where) : ("已发送到 " + where + "：文字 + 图片各一条"), data);
        }
        if (textOk && !imgOk) {
            return AjaxResult.error("文字已发出，但图片失败：" + imgRes.get("errmsg"), data);
        }
        return AjaxResult.error("文字发送失败：" + textRes.get("errmsg") + "（errcode=" + textRes.get("errcode") + "）", data);
    }

    /**
     * 上传一张图片，返回可公开访问的 URL，供手动推送正文引用。
     *
     * 为什么要走这条而不是 image 消息：
     *   企业微信一条消息只能有一个 msgtype；而普通微信（微信插件）只稳定渲染 text，
     *   markdown 实测会显示「暂不支持此消息类型」。所以「文字 + 图片」做成
     *   「纯文本正文 + 图片链接」——微信里一定收得到，点链接即可看图。
     */
    @PreAuthorize("@ss.hasPermi('system:push:send')")
    @Log(title = "手动推送", businessType = BusinessType.OTHER)
    @PostMapping("/uploadImage")
    public AjaxResult uploadImage(@RequestBody Map<String, Object> body) {
        try {
            String data = str(body.get("data"), "");
            if (data.length() < 100) {
                return AjaxResult.error("图片内容为空");
            }
            if (data.length() > 18 * 1024 * 1024) {
                return AjaxResult.error("图片过大，请压缩后再传（上限约 12MB）");
            }
            java.util.regex.Matcher m = java.util.regex.Pattern
                    .compile("^data:image/([A-Za-z]+);base64,(.+)$", java.util.regex.Pattern.DOTALL)
                    .matcher(data);
            if (!m.matches()) {
                return AjaxResult.error("不是有效的图片数据");
            }
            String ext = m.group(1).toLowerCase();
            if (!Arrays.asList("png", "jpg", "jpeg", "gif", "webp").contains(ext)) {
                return AjaxResult.error("只支持 png / jpg / gif / webp");
            }
            byte[] raw = java.util.Base64.getDecoder().decode(m.group(2));
            if (raw.length > PUSH_IMG_MAX) {
                return AjaxResult.error("图片超过 12MB（当前 " + (raw.length / 1024 / 1024) + "MB）");
            }
            java.io.File dir = new java.io.File(PUSH_IMG_DIR);
            if (!dir.exists() && !dir.mkdirs()) {
                return AjaxResult.error("无法创建图片目录：" + PUSH_IMG_DIR);
            }
            String name = UUID.randomUUID().toString().replace("-", "").substring(0, 16)
                    + "." + ("jpeg".equals(ext) ? "jpg" : ext);
            java.io.File f = new java.io.File(dir, name);
            java.nio.file.Files.write(f.toPath(), raw);
            try {
                java.nio.file.Files.setPosixFilePermissions(f.toPath(),
                        java.nio.file.attribute.PosixFilePermissions.fromString("rw-r--r--"));
            } catch (Exception ignored) {
            }
            Map<String, Object> data2 = new LinkedHashMap<>();
            data2.put("url", PUSH_IMG_BASE + name);
            data2.put("bytes", raw.length);
            return success(data2);
        } catch (Exception e) {
            return AjaxResult.error("上传失败：" + e.getMessage());
        }
    }

    /** 预览：把标题+正文拼成最终发出去的样子 */
    @PreAuthorize("@ss.hasPermi('system:push:send')")
    @PostMapping("/preview")
    public AjaxResult preview(@RequestBody Map<String, Object> body) {
        String title = str(body.get("title"), "");
        String content = str(body.get("content"), "");
        StringBuilder sb = new StringBuilder();
        if (!title.trim().isEmpty()) {
            sb.append("【").append(title.trim()).append("】\n\n");
        }
        sb.append(content.trim());
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("text", sb.toString());
        data.put("bytes", sb.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8).length);
        return success(data);
    }

    private String str(Object o, String def) {
        return o == null ? def : String.valueOf(o);
    }
}
