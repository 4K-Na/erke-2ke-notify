package com.ruoyi.system.domain;

import java.math.BigDecimal;
import org.apache.commons.lang3.builder.ToStringBuilder;
import org.apache.commons.lang3.builder.ToStringStyle;
import com.ruoyi.common.annotation.Excel;
import com.ruoyi.common.core.domain.BaseEntity;

/**
 * 通知订阅者对象 t_subscriber
 * 
 * @author ruoyi
 * @date 2026-10-21
 */
public class TSubscriber extends BaseEntity
{
    private static final long serialVersionUID = 1L;

    /** 订阅者ID */
    private Long subscriberId;

    /** 通道 wxpusher/wecom/email */
    @Excel(name = "通道 wxpusher/wecom/email")
    private String channel;

    /** 外部ID */
    @Excel(name = "外部ID")
    private String externalId;

    /** 昵称 */
    @Excel(name = "昵称")
    private String nickname;

    /** 真实姓名 */
    @Excel(name = "真实姓名")
    private String realName;

    /** 班级 */
    @Excel(name = "班级")
    private String className;

    /** 关键词过滤 */
    @Excel(name = "关键词过滤")
    private String keywords;

    /** 学分下限 */
    @Excel(name = "学分下限")
    private BigDecimal minCredit;

    /** 只看校级 0否1是 */
    @Excel(name = "只看校级 0否1是")
    private String onlySchool;

    /** 静默时段 */
    @Excel(name = "静默时段")
    private String quietHours;

    /** 状态 0正常1停用 */
    @Excel(name = "状态 0正常1停用")
    private String status;

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

    public void setExternalId(String externalId) 
    {
        this.externalId = externalId;
    }

    public String getExternalId() 
    {
        return externalId;
    }

    public void setNickname(String nickname) 
    {
        this.nickname = nickname;
    }

    public String getNickname() 
    {
        return nickname;
    }

    public void setRealName(String realName) 
    {
        this.realName = realName;
    }

    public String getRealName() 
    {
        return realName;
    }

    public void setClassName(String className) 
    {
        this.className = className;
    }

    public String getClassName() 
    {
        return className;
    }

    public void setKeywords(String keywords) 
    {
        this.keywords = keywords;
    }

    public String getKeywords() 
    {
        return keywords;
    }

    public void setMinCredit(BigDecimal minCredit) 
    {
        this.minCredit = minCredit;
    }

    public BigDecimal getMinCredit() 
    {
        return minCredit;
    }

    public void setOnlySchool(String onlySchool) 
    {
        this.onlySchool = onlySchool;
    }

    public String getOnlySchool() 
    {
        return onlySchool;
    }

    public void setQuietHours(String quietHours) 
    {
        this.quietHours = quietHours;
    }

    public String getQuietHours() 
    {
        return quietHours;
    }

    public void setStatus(String status) 
    {
        this.status = status;
    }

    public String getStatus() 
    {
        return status;
    }

    @Override
    public String toString() {
        return new ToStringBuilder(this,ToStringStyle.MULTI_LINE_STYLE)
            .append("subscriberId", getSubscriberId())
            .append("channel", getChannel())
            .append("externalId", getExternalId())
            .append("nickname", getNickname())
            .append("realName", getRealName())
            .append("className", getClassName())
            .append("keywords", getKeywords())
            .append("minCredit", getMinCredit())
            .append("onlySchool", getOnlySchool())
            .append("quietHours", getQuietHours())
            .append("status", getStatus())
            .append("createBy", getCreateBy())
            .append("createTime", getCreateTime())
            .append("updateBy", getUpdateBy())
            .append("updateTime", getUpdateTime())
            .append("remark", getRemark())
            .toString();
    }
}
