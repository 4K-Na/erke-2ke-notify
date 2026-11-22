package com.ruoyi.system.service;

import java.util.List;
import com.ruoyi.system.domain.TNotice;

/**
 * 公告Service接口
 * 
 * @author ruoyi
 * @date 2026-10-21
 */
public interface ITNoticeService 
{
    /**
     * 查询公告
     * 
     * @param noticeId 公告主键
     * @return 公告
     */
    public TNotice selectTNoticeByNoticeId(Long noticeId);

    /**
     * 查询公告列表
     * 
     * @param tNotice 公告
     * @return 公告集合
     */
    public List<TNotice> selectTNoticeList(TNotice tNotice);

    /**
     * 新增公告
     * 
     * @param tNotice 公告
     * @return 结果
     */
    public int insertTNotice(TNotice tNotice);

    /**
     * 修改公告
     * 
     * @param tNotice 公告
     * @return 结果
     */
    public int updateTNotice(TNotice tNotice);

    /**
     * 批量删除公告
     * 
     * @param noticeIds 需要删除的公告主键集合
     * @return 结果
     */
    public int deleteTNoticeByNoticeIds(Long[] noticeIds);

    /**
     * 删除公告信息
     * 
     * @param noticeId 公告主键
     * @return 结果
     */
    public int deleteTNoticeByNoticeId(Long noticeId);

    /** 公开公告：状态正常且在有效期内 */
    public List<TNotice> selectPublicNotices();
}
