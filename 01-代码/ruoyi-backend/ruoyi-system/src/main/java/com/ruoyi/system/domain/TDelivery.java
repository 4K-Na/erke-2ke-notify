package com.ruoyi.system.domain;

import java.util.Date;
import com.fasterxml.jackson.annotation.JsonFormat;
import org.apache.commons.lang3.builder.ToStringBuilder;
import org.apache.commons.lang3.builder.ToStringStyle;
import com.ruoyi.common.annotation.Excel;
import com.ruoyi.common.core.domain.BaseEntity;

/**
 * 通知投递记录对象 t_delivery
 * 
 * @author ruoyi
 * @date 2026-10-21
 */
public class TDelivery extends BaseEntity
{
    private static final long serialVersionUID = 1L;

    /** 投递ID */
    private Long deliveryId;

    /** 活动ID */
    @Excel(name = "活动ID")
    private String activityId;

    /** 活动标题快照 */
    @Excel(name = "活动标题快照")
    private String activityTitle;

    /** 订阅者名称快照 */
    @Excel(name = "订阅者")
    private String subscriberName;

    /** 订阅者ID */
    @Excel(name = "订阅者ID")
    private Long subscriberId;

    /** 通道 */
    @Excel(name = "通道")
    private String channel;

    /** pending/sent/failed */
    @Excel(name = "pending/sent/failed")
    private String sendStatus;

    /** 尝试次数 */
    @Excel(name = "尝试次数")
    private Long attempt;

    /** 错误信息 */
    @Excel(name = "错误信息")
    private String lastError;

    /** 发送时间 */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    @Excel(name = "发送时间", width = 30, dateFormat = "yyyy-MM-dd HH:mm:ss")
    private Date sentTime;

    public void setDeliveryId(Long deliveryId) 
    {
        this.deliveryId = deliveryId;
    }

    public Long getDeliveryId() 
    {
        return deliveryId;
    }

    public void setActivityId(String activityId) 
    {
        this.activityId = activityId;
    }

    public String getActivityId() 
    {
        return activityId;
    }

    public void setActivityTitle(String activityTitle) 
    {
        this.activityTitle = activityTitle;
    }

    public String getActivityTitle() 
    {
        return activityTitle;
    }

    public void setSubscriberId(Long subscriberId) 
    {
        this.subscriberId = subscriberId;
    }

    public Long getSubscriberId() 
    {
        return subscriberId;
    }

    public void setChannel(String channel) 
    {
        this.channel = channel;
    }

    public String getChannel() 
    {
        return channel;
    }

    public void setSendStatus(String sendStatus) 
    {
        this.sendStatus = sendStatus;
    }

    public String getSendStatus() 
    {
        return sendStatus;
    }

    public void setAttempt(Long attempt) 
    {
        this.attempt = attempt;
    }

    public Long getAttempt() 
    {
        return attempt;
    }

    public void setLastError(String lastError) 
    {
        this.lastError = lastError;
    }

    public String getLastError() 
    {
        return lastError;
    }

    public void setSentTime(Date sentTime) 
    {
        this.sentTime = sentTime;
    }

    public Date getSentTime() 
    {
        return sentTime;
    }

    @Override
    public String toString() {
        return new ToStringBuilder(this,ToStringStyle.MULTI_LINE_STYLE)
            .append("deliveryId", getDeliveryId())
            .append("activityId", getActivityId())
            .append("activityTitle", getActivityTitle())
            .append("subscriberId", getSubscriberId())
            .append("channel", getChannel())
            .append("sendStatus", getSendStatus())
            .append("attempt", getAttempt())
            .append("lastError", getLastError())
            .append("sentTime", getSentTime())
            .append("createBy", getCreateBy())
            .append("createTime", getCreateTime())
            .append("updateBy", getUpdateBy())
            .append("updateTime", getUpdateTime())
            .append("remark", getRemark())
            .toString();
    }


    public String getSubscriberName() {
        return subscriberName;
    }

    public void setSubscriberName(String subscriberName) {
        this.subscriberName = subscriberName;
    }
}
