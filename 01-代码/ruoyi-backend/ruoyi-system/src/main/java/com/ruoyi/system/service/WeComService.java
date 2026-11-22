package com.ruoyi.system.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.io.File;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 企业微信消息发送服务。
 *
 * 配置复用 Python 那边的 /opt/2ke-hub/wecom.json，避免两处维护。
 * token 带内存缓存（提前 5 分钟过期），失败不抛给前端裸异常，返回结构化结果。
 */
@Service
public class WeComService {

    private static final Logger log = LoggerFactory.getLogger(WeComService.class);

    private static final String CONFIG_PATH = "/opt/2ke-hub/wecom.json";
    private static final String API = "https://qyapi.weixin.qq.com/cgi-bin";

    private final HttpClient http = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build();
    private final ObjectMapper mapper = new ObjectMapper();

    private String cachedToken;
    private long tokenExpireAt = 0L;

    /** 读配置；每次调用都读文件，便于后台改完即时生效（文件很小，开销可忽略） */
    private JsonNode loadConfig() throws Exception {
        File f = new File(CONFIG_PATH);
        if (!f.exists()) {
            throw new IllegalStateException("找不到企业微信配置：" + CONFIG_PATH);
        }
        return mapper.readTree(f);
    }

    public synchronized String getToken() throws Exception {
        long now = System.currentTimeMillis();
        if (cachedToken != null && now < tokenExpireAt) {
            return cachedToken;
        }
        JsonNode c = loadConfig();
        String url = API + "/gettoken?corpid=" + c.path("corp_id").asText()
                + "&corpsecret=" + c.path("secret").asText();
        HttpRequest req = HttpRequest.newBuilder(URI.create(url))
                .timeout(Duration.ofSeconds(15)).GET().build();
        HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        JsonNode r = mapper.readTree(resp.body());
        if (r.path("errcode").asInt(-1) != 0) {
            throw new IllegalStateException("获取 access_token 失败：" + resp.body());
        }
        cachedToken = r.path("access_token").asText();
        tokenExpireAt = now + (r.path("expires_in").asLong(7200) - 300) * 1000L;
        return cachedToken;
    }

    /** 应用可见范围内的管理员 userid（用于"发给自己"） */
    public String getAdminUserid() {
        try {
            String v = loadConfig().path("admin_userid").asText();
            return (v == null || v.isEmpty()) ? null : v;
        } catch (Exception e) {
            return null;
        }
    }

    /**
     * 上传图片到企业微信临时素材库，返回 media_id（企业微信侧保留 3 天）。
     * media/upload 要 multipart/form-data，HttpClient 得手写 body。
     */
    public String uploadImage(byte[] data) throws Exception {
        String tk = getToken();
        String boundary = "----RuoYi2ke" + System.currentTimeMillis();
        java.io.ByteArrayOutputStream bos = new java.io.ByteArrayOutputStream();
        bos.write(("--" + boundary + "\r\n").getBytes(StandardCharsets.UTF_8));
        bos.write(("Content-Disposition: form-data; name=\"media\"; filename=\"image.png\"; filelength="
                + data.length + "\r\n").getBytes(StandardCharsets.UTF_8));
        bos.write("Content-Type: application/octet-stream\r\n\r\n".getBytes(StandardCharsets.UTF_8));
        bos.write(data);
        bos.write(("\r\n--" + boundary + "--\r\n").getBytes(StandardCharsets.UTF_8));

        HttpRequest req = HttpRequest.newBuilder(
                        URI.create(API + "/media/upload?access_token=" + tk + "&type=image"))
                .timeout(Duration.ofSeconds(30))
                .header("Content-Type", "multipart/form-data; boundary=" + boundary)
                .POST(HttpRequest.BodyPublishers.ofByteArray(bos.toByteArray()))
                .build();
        HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        JsonNode r = mapper.readTree(resp.body());
        int code = r.path("errcode").asInt(0);
        if (code != 0) {
            throw new RuntimeException("上传素材失败 errcode=" + code + " " + r.path("errmsg").asText(""));
        }
        return r.path("media_id").asText();
    }

    /**
     * 发送图片消息（msgtype=image）。
     * 注意：企业微信一条消息只能一个类型，所以「文字 + 图片」= 先 sendText 再 sendImage，两条。
     */
    public Map<String, Object> sendImage(String touser, String mediaId) {
        Map<String, Object> out = new LinkedHashMap<>();
        try {
            String tk = getToken();
            JsonNode c = loadConfig();
            int agentId = c.path("agent_id").asInt();

            Map<String, Object> image = new LinkedHashMap<>();
            image.put("media_id", mediaId);

            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("touser", touser);
            payload.put("msgtype", "image");
            payload.put("agentid", agentId);
            payload.put("image", image);
            payload.put("safe", 0);

            String body = mapper.writeValueAsString(payload);
            HttpRequest req = HttpRequest.newBuilder(
                            URI.create(API + "/message/send?access_token=" + tk))
                    .timeout(Duration.ofSeconds(20))
                    .header("Content-Type", "application/json; charset=utf-8")
                    .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                    .build();
            HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            JsonNode r = mapper.readTree(resp.body());
            int code = r.path("errcode").asInt(-1);
            out.put("ok", code == 0);
            out.put("errcode", code);
            out.put("errmsg", r.path("errmsg").asText(""));
            out.put("invaliduser", r.path("invaliduser").asText(""));
            out.put("msgid", r.path("msgid").asText(""));
            if (code != 0) {
                out.put("raw", resp.body());
                log.warn("企业微信发图片失败 touser={} code={} msg={}", touser, code, out.get("errmsg"));
            }
            return out;
        } catch (Exception e) {
            log.error("企业微信发图片异常 touser={}", touser, e);
            out.put("ok", false);
            out.put("errcode", -1);
            out.put("errmsg", e.getMessage());
            return out;
        }
    }

    /**
     * 发送纯文本消息。
     *
     * @param touser  "userId1|userId2" 或 "@all"
     * @return 结构化结果：ok / errcode / errmsg / invaliduser / msgid / raw
     */
    public Map<String, Object> sendText(String touser, String content) {
        Map<String, Object> out = new LinkedHashMap<>();
        try {
            String tk = getToken();
            JsonNode c = loadConfig();
            int agentId = c.path("agent_id").asInt();

            Map<String, Object> text = new LinkedHashMap<>();
            text.put("content", content);

            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("touser", touser);
            payload.put("msgtype", "text");
            payload.put("agentid", agentId);
            payload.put("text", text);
            payload.put("safe", 0);

            String body = mapper.writeValueAsString(payload);
            HttpRequest req = HttpRequest.newBuilder(
                            URI.create(API + "/message/send?access_token=" + tk))
                    .timeout(Duration.ofSeconds(20))
                    .header("Content-Type", "application/json; charset=utf-8")
                    .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                    .build();
            HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            JsonNode r = mapper.readTree(resp.body());

            int code = r.path("errcode").asInt(-1);
            out.put("ok", code == 0);
            out.put("errcode", code);
            out.put("errmsg", r.path("errmsg").asText(""));
            out.put("invaliduser", r.path("invaliduser").asText(""));
            out.put("msgid", r.path("msgid").asText(""));
            if (code != 0) {
                out.put("raw", resp.body());
                log.warn("企业微信发送失败 touser={} code={} msg={}", touser, code, out.get("errmsg"));
            }
            return out;
        } catch (Exception e) {
            log.error("企业微信发送异常 touser={}", touser, e);
            out.put("ok", false);
            out.put("errcode", -1);
            out.put("errmsg", e.getMessage());
            return out;
        }
    }
}
