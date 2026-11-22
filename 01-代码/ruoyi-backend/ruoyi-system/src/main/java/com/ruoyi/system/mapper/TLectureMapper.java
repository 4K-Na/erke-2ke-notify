package com.ruoyi.system.mapper;

import com.ruoyi.system.domain.TLecture;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.util.List;
import java.util.Map;

/**
 * 讲座查询（只读）。数据由外部采集器写入，后台不提供增删改，
 * 因此这里只有 SELECT —— 用注解写，避免再经历一次 XML 位置放错导致启动崩溃。
 */
@Mapper
public interface TLectureMapper {

    @Select("<script>"
            + "SELECT lecture_id AS lectureId, title, lecturer, lecture_type AS lectureType,"
            + " department, place,"
            + " DATE_FORMAT(open_start,'%Y-%m-%d %H:%i') AS openStart,"
            + " DATE_FORMAT(open_end,'%Y-%m-%d %H:%i') AS openEnd,"
            + " DATE_FORMAT(enroll_start,'%Y-%m-%d %H:%i') AS enrollStart,"
            + " DATE_FORMAT(enroll_end,'%Y-%m-%d %H:%i') AS enrollEnd,"
            + " upper_limit AS upperLimit, enroll_count AS enrollCount, report_count AS reportCount,"
            + " biz_type AS bizType, semester, act_state AS actState,"
            + " content_text AS contentText, teacher_text AS teacherText,"
            + " DATE_FORMAT(first_seen,'%Y-%m-%d %H:%i') AS firstSeen,"
            + " DATE_FORMAT(last_seen,'%Y-%m-%d %H:%i') AS lastSeen"
            + " FROM t_lecture"
            + " <where>"
            + "  <if test='q.title != null and q.title != \"\"'> AND title LIKE CONCAT('%', #{q.title}, '%')</if>"
            + "  <if test='q.lecturer != null and q.lecturer != \"\"'> AND lecturer LIKE CONCAT('%', #{q.lecturer}, '%')</if>"
            + "  <if test='q.lectureType != null and q.lectureType != \"\"'> AND lecture_type = #{q.lectureType}</if>"
            + "  <if test='q.stateFilter != null and q.stateFilter != \"\"'> AND act_state = #{q.stateFilter}</if>"
            + " </where>"
            + " ORDER BY act_state = 'open' DESC, open_start ASC"
            + "</script>")
    List<TLecture> selectLectureList(@Param("q") TLecture q);

    @Select("SELECT lecture_type AS name, COUNT(*) AS cnt FROM t_lecture"
            + " WHERE lecture_type IS NOT NULL AND lecture_type <> ''"
            + " GROUP BY lecture_type ORDER BY cnt DESC")
    List<Map<String, Object>> selectTypeOptions();

    @Select("SELECT"
            + " COUNT(*) AS total,"
            + " SUM(act_state = 'open') AS openCnt,"
            + " SUM(act_state = 'ended') AS endedCnt,"
            + " SUM(act_state = 'open' AND (upper_limit IS NULL OR enroll_count < upper_limit)) AS canJoinCnt,"
            + " MAX(last_seen) AS lastSeen"
            + " FROM t_lecture")
    Map<String, Object> selectLectureStat();

    @Update("UPDATE t_lecture SET act_state = 'ended' WHERE open_end IS NOT NULL AND open_end < NOW()")
    int closeExpired();
    /** 推送记录（分页，支持按讲座名/状态筛） */
    @Select("<script>"
            + "SELECT delivery_id AS deliveryId, lecture_id AS lectureId,"
            + " lecture_title AS lectureTitle, subscriber_name AS subscriberName,"
            + " external_id AS externalId, send_status AS sendStatus, attempt,"
            + " last_error AS lastError,"
            + " DATE_FORMAT(create_time,'%m-%d %H:%i:%s') AS createTime,"
            + " DATE_FORMAT(sent_time,'%m-%d %H:%i:%s') AS sentTime"
            + " FROM t_lecture_delivery"
            + " <where>"
            + "  <if test='q.lectureTitle != null and q.lectureTitle != \"\"'>"
            + "    AND lecture_title LIKE CONCAT('%', #{q.lectureTitle}, '%')</if>"
            + "  <if test='q.sendStatus != null and q.sendStatus != \"\"'>"
            + "    AND send_status = #{q.sendStatus}</if>"
            + "  <if test='q.subscriberName != null and q.subscriberName != \"\"'>"
            + "    AND subscriber_name LIKE CONCAT('%', #{q.subscriberName}, '%')</if>"
            + " </where>"
            + " ORDER BY delivery_id DESC"
            + "</script>")
    List<Map<String, Object>> selectDeliveryList(@Param("q") Map<String, Object> q);

    /** 推送状态统计 */
    @Select("SELECT send_status AS name, COUNT(*) AS cnt"
            + " FROM t_lecture_delivery GROUP BY send_status")
    List<Map<String, Object>> selectDeliveryStat();
}
