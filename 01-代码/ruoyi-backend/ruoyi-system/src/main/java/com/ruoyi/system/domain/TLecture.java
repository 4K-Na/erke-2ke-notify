package com.ruoyi.system.domain;

import com.ruoyi.common.annotation.Excel;
import com.ruoyi.common.core.domain.BaseEntity;

/**
 * 集大教务讲座（jwxt / EAMS）。
 * 数据由 /opt/jwxt/collector_jwxt.py 定时采集写入，后台只读。
 */
public class TLecture extends BaseEntity {

    private static final long serialVersionUID = 1L;

    /** 讲座ID（jwxt lecture.id） */
    private Long lectureId;

    @Excel(name = "讲座名")
    private String title;

    @Excel(name = "主讲人")
    private String lecturer;

    @Excel(name = "类型")
    private String lectureType;

    @Excel(name = "主办学院")
    private String department;

    @Excel(name = "地点")
    private String place;

    @Excel(name = "开始时间")
    private String openStart;

    private String openEnd;

    @Excel(name = "报名开始")
    private String enrollStart;

    @Excel(name = "报名截止")
    private String enrollEnd;

    @Excel(name = "名额")
    private Integer upperLimit;

    @Excel(name = "已报名")
    private Integer enrollCount;

    private Integer reportCount;

    private String bizType;

    private String semester;

    private String actState;

    private String contentText;

    private String teacherText;

    private String firstSeen;

    private String lastSeen;

    /** 查询用：只看某个状态 */
    private String stateFilter;

    public Long getLectureId() { return lectureId; }
    public void setLectureId(Long lectureId) { this.lectureId = lectureId; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public String getLecturer() { return lecturer; }
    public void setLecturer(String lecturer) { this.lecturer = lecturer; }

    public String getLectureType() { return lectureType; }
    public void setLectureType(String lectureType) { this.lectureType = lectureType; }

    public String getDepartment() { return department; }
    public void setDepartment(String department) { this.department = department; }

    public String getPlace() { return place; }
    public void setPlace(String place) { this.place = place; }

    public String getOpenStart() { return openStart; }
    public void setOpenStart(String openStart) { this.openStart = openStart; }

    public String getOpenEnd() { return openEnd; }
    public void setOpenEnd(String openEnd) { this.openEnd = openEnd; }

    public String getEnrollStart() { return enrollStart; }
    public void setEnrollStart(String enrollStart) { this.enrollStart = enrollStart; }

    public String getEnrollEnd() { return enrollEnd; }
    public void setEnrollEnd(String enrollEnd) { this.enrollEnd = enrollEnd; }

    public Integer getUpperLimit() { return upperLimit; }
    public void setUpperLimit(Integer upperLimit) { this.upperLimit = upperLimit; }

    public Integer getEnrollCount() { return enrollCount; }
    public void setEnrollCount(Integer enrollCount) { this.enrollCount = enrollCount; }

    public Integer getReportCount() { return reportCount; }
    public void setReportCount(Integer reportCount) { this.reportCount = reportCount; }

    public String getBizType() { return bizType; }
    public void setBizType(String bizType) { this.bizType = bizType; }

    public String getSemester() { return semester; }
    public void setSemester(String semester) { this.semester = semester; }

    public String getActState() { return actState; }
    public void setActState(String actState) { this.actState = actState; }

    public String getContentText() { return contentText; }
    public void setContentText(String contentText) { this.contentText = contentText; }

    public String getTeacherText() { return teacherText; }
    public void setTeacherText(String teacherText) { this.teacherText = teacherText; }

    public String getFirstSeen() { return firstSeen; }
    public void setFirstSeen(String firstSeen) { this.firstSeen = firstSeen; }

    public String getLastSeen() { return lastSeen; }
    public void setLastSeen(String lastSeen) { this.lastSeen = lastSeen; }

    public String getStateFilter() { return stateFilter; }
    public void setStateFilter(String stateFilter) { this.stateFilter = stateFilter; }
}
