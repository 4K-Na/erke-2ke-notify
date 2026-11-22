package com.ruoyi.system.domain;

import java.util.Date;
import com.fasterxml.jackson.annotation.JsonFormat;
import org.apache.commons.lang3.builder.ToStringBuilder;
import org.apache.commons.lang3.builder.ToStringStyle;
import com.ruoyi.common.annotation.Excel;
import com.ruoyi.common.core.domain.BaseEntity;

/**
 * 公告对象 t_notice
 * 
 * @author ruoyi
 * @date 2026-10-21
 */
public class TNotice extends BaseEntity
{
    private static final long serialVersionUID = 1L;

    /** 公告ID */
    private Long noticeId;

    /** 标题 */
    @Excel(name = "标题")
    private String title;

    /** 正文 */
    @Excel(name = "正文")
    private String content;

    /** 置顶 0否1是 */
    @Excel(name = "置顶 0否1是")
    private String pinned;

    /** 生效时间 */
    @JsonFormat(pattern = "yyyy-MM-dd")
    @Excel(name = "生效时间", width = 30, dateFormat = "yyyy-MM-dd")
    private Date validFrom;

    /** 失效时间 */
    @JsonFormat(pattern = "yyyy-MM-dd")
    @Excel(name = "失效时间", width = 30, dateFormat = "yyyy-MM-dd")
    private Date validTo;

    /** 状态 0显示1隐藏 */
    @Excel(name = "状态 0显示1隐藏")
    private String status;

    /** 排序 */
    @Excel(name = "排序")
    private Integer sortNo;

    public void setNoticeId(Long noticeId) 
    {
        this.noticeId = noticeId;
    }

    public Long getNoticeId() 
    {
        return noticeId;
    }

    public void setTitle(String title) 
    {
        this.title = title;
    }

    public String getTitle() 
    {
        return title;
    }

    public void setContent(String content) 
    {
        this.content = content;
    }

    public String getContent() 
    {
        return content;
    }

    public void setPinned(String pinned) 
    {
        this.pinned = pinned;
    }

    public String getPinned() 
    {
        return pinned;
    }

    public void setValidFrom(Date validFrom) 
    {
        this.validFrom = validFrom;
    }

    public Date getValidFrom() 
    {
        return validFrom;
    }

    public void setValidTo(Date validTo) 
    {
        this.validTo = validTo;
    }

    public Date getValidTo() 
    {
        return validTo;
    }

    public void setStatus(String status) 
    {
        this.status = status;
    }

    public String getStatus() 
    {
        return status;
    }

    public void setSortNo(Integer sortNo) 
    {
        this.sortNo = sortNo;
    }

    public Integer getSortNo() 
    {
        return sortNo;
    }

    @Override
    public String toString() {
        return new ToStringBuilder(this,ToStringStyle.MULTI_LINE_STYLE)
            .append("noticeId", getNoticeId())
            .append("title", getTitle())
            .append("content", getContent())
            .append("pinned", getPinned())
            .append("validFrom", getValidFrom())
            .append("validTo", getValidTo())
            .append("status", getStatus())
            .append("sortNo", getSortNo())
            .append("createBy", getCreateBy())
            .append("createTime", getCreateTime())
            .append("updateBy", getUpdateBy())
            .append("updateTime", getUpdateTime())
            .append("remark", getRemark())
            .toString();
    }
}
