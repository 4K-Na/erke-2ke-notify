package com.ruoyi.system.domain;

import java.math.BigDecimal;
import java.util.Date;
import com.fasterxml.jackson.annotation.JsonFormat;
import org.apache.commons.lang3.builder.ToStringBuilder;
import org.apache.commons.lang3.builder.ToStringStyle;
import com.ruoyi.common.annotation.Excel;
import com.ruoyi.common.core.domain.BaseEntity;

/**
 * 第二课堂活动对象 t_activity
 * 
 * @author ruoyi
 * @date 2026-10-21
 */
public class TActivity extends BaseEntity
{
    private static final long serialVersionUID = 1L;

    /** 2ke活动ID */
    private String activityId;

    /** 活动标题 */
    @Excel(name = "活动标题")
    private String title;

    /** 级别 yard/school */
    @Excel(name = "级别 yard/school")
    private String activityType;

    /** 级别名称 */
    @Excel(name = "级别名称")
    private String activityTypeLabel;

    /** 主办学院 */
    @Excel(name = "主办学院")
    private String deptLabel;

    /** 创建学院 */
    @Excel(name = "创建学院")
    private String creatorCollege;

    /** 总学分 */
    @Excel(name = "总学分")
    private BigDecimal creditTotal;

    /** 学分明细JSON */
    @Excel(name = "学分明细JSON")
    private String creditDetail;

    /** 学分类别 */
    @Excel(name = "学分类别")
    private String creditTypeName;

    /** 开始时间 */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    @Excel(name = "开始时间", width = 30, dateFormat = "yyyy-MM-dd HH:mm:ss")
    private Date startAt;

    /** 结束时间 */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    @Excel(name = "结束时间", width = 30, dateFormat = "yyyy-MM-dd HH:mm:ss")
    private Date endAt;

    /** 报名开始 */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    @Excel(name = "报名开始", width = 30, dateFormat = "yyyy-MM-dd HH:mm:ss")
    private Date signinStart;

    /** 报名截止 */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    @Excel(name = "报名截止", width = 30, dateFormat = "yyyy-MM-dd HH:mm:ss")
    private Date signinEnd;

    /** 报名方式 */
    @Excel(name = "报名方式")
    private String signupWay;

    /** 活动地点 */
    @Excel(name = "活动地点")
    private String address;

    /** 名额 */
    @Excel(name = "名额")
    private Long quota;

    /** 状态 open/ended */
    @Excel(name = "状态 open/ended")
    private String actState;

    /** 首次发现 */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    @Excel(name = "首次发现", width = 30, dateFormat = "yyyy-MM-dd HH:mm:ss")
    private Date firstSeen;

    /** 最近同步 */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    @Excel(name = "最近同步", width = 30, dateFormat = "yyyy-MM-dd HH:mm:ss")
    private Date lastSeen;

    /** 原始JSON */
    @Excel(name = "原始JSON")
    private String rawJson;

    public void setActivityId(String activityId) 
    {
        this.activityId = activityId;
    }

    public String getActivityId() 
    {
        return activityId;
    }

    public void setTitle(String title) 
    {
        this.title = title;
    }

    public String getTitle() 
    {
        return title;
    }

    public void setActivityType(String activityType) 
    {
        this.activityType = activityType;
    }

    public String getActivityType() 
    {
        return activityType;
    }

    public void setActivityTypeLabel(String activityTypeLabel) 
    {
        this.activityTypeLabel = activityTypeLabel;
    }

    public String getActivityTypeLabel() 
    {
        return activityTypeLabel;
    }

    public void setDeptLabel(String deptLabel) 
    {
        this.deptLabel = deptLabel;
    }

    public String getDeptLabel() 
    {
        return deptLabel;
    }

    public void setCreatorCollege(String creatorCollege) 
    {
        this.creatorCollege = creatorCollege;
    }

    public String getCreatorCollege() 
    {
        return creatorCollege;
    }

    public void setCreditTotal(BigDecimal creditTotal) 
    {
        this.creditTotal = creditTotal;
    }

    public BigDecimal getCreditTotal() 
    {
        return creditTotal;
    }

    public void setCreditDetail(String creditDetail) 
    {
        this.creditDetail = creditDetail;
    }

    public String getCreditDetail() 
    {
        return creditDetail;
    }

    public void setCreditTypeName(String creditTypeName) 
    {
        this.creditTypeName = creditTypeName;
    }

    public String getCreditTypeName() 
    {
        return creditTypeName;
    }

    public void setStartAt(Date startAt) 
    {
        this.startAt = startAt;
    }

    public Date getStartAt() 
    {
        return startAt;
    }

    public void setEndAt(Date endAt) 
    {
        this.endAt = endAt;
    }

    public Date getEndAt() 
    {
        return endAt;
    }

    public void setSigninStart(Date signinStart) 
    {
        this.signinStart = signinStart;
    }

    public Date getSigninStart() 
    {
        return signinStart;
    }

    public void setSigninEnd(Date signinEnd) 
    {
        this.signinEnd = signinEnd;
    }

    public Date getSigninEnd() 
    {
        return signinEnd;
    }

    public void setSignupWay(String signupWay) 
    {
        this.signupWay = signupWay;
    }

    public String getSignupWay() 
    {
        return signupWay;
    }

    public void setAddress(String address) 
    {
        this.address = address;
    }

    public String getAddress() 
    {
        return address;
    }

    public void setQuota(Long quota) 
    {
        this.quota = quota;
    }

    public Long getQuota() 
    {
        return quota;
    }

    public void setActState(String actState) 
    {
        this.actState = actState;
    }

    public String getActState() 
    {
        return actState;
    }

    public void setFirstSeen(Date firstSeen) 
    {
        this.firstSeen = firstSeen;
    }

    public Date getFirstSeen() 
    {
        return firstSeen;
    }

    public void setLastSeen(Date lastSeen) 
    {
        this.lastSeen = lastSeen;
    }

    public Date getLastSeen() 
    {
        return lastSeen;
    }

    public void setRawJson(String rawJson) 
    {
        this.rawJson = rawJson;
    }

    public String getRawJson() 
    {
        return rawJson;
    }

    @Override
    public String toString() {
        return new ToStringBuilder(this,ToStringStyle.MULTI_LINE_STYLE)
            .append("activityId", getActivityId())
            .append("title", getTitle())
            .append("activityType", getActivityType())
            .append("activityTypeLabel", getActivityTypeLabel())
            .append("deptLabel", getDeptLabel())
            .append("creatorCollege", getCreatorCollege())
            .append("creditTotal", getCreditTotal())
            .append("creditDetail", getCreditDetail())
            .append("creditTypeName", getCreditTypeName())
            .append("startAt", getStartAt())
            .append("endAt", getEndAt())
            .append("signinStart", getSigninStart())
            .append("signinEnd", getSigninEnd())
            .append("signupWay", getSignupWay())
            .append("address", getAddress())
            .append("quota", getQuota())
            .append("actState", getActState())
            .append("firstSeen", getFirstSeen())
            .append("lastSeen", getLastSeen())
            .append("rawJson", getRawJson())
            .append("createBy", getCreateBy())
            .append("createTime", getCreateTime())
            .append("updateBy", getUpdateBy())
            .append("updateTime", getUpdateTime())
            .append("remark", getRemark())
            .toString();
    }
}
