package com.ruoyi.system.service.impl;

import java.util.List;
import com.ruoyi.common.utils.DateUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.ruoyi.system.mapper.TNoticeMapper;
import com.ruoyi.system.domain.TNotice;
import com.ruoyi.system.service.ITNoticeService;

/**
 * 公告Service业务层处理
 * 
 * @author ruoyi
 * @date 2026-10-21
 */
@Service
public class TNoticeServiceImpl implements ITNoticeService 
{
    @Autowired
    private TNoticeMapper tNoticeMapper;

    /**
     * 查询公告
     * 
     * @param noticeId 公告主键
     * @return 公告
     */
    @Override
    public TNotice selectTNoticeByNoticeId(Long noticeId)
    {
        return tNoticeMapper.selectTNoticeByNoticeId(noticeId);
    }

    /**
     * 查询公告列表
     * 
     * @param tNotice 公告
     * @return 公告
     */
    @Override
    public List<TNotice> selectTNoticeList(TNotice tNotice)
    {
        return tNoticeMapper.selectTNoticeList(tNotice);
    }

    /**
     * 新增公告
     * 
     * @param tNotice 公告
     * @return 结果
     */
    @Override
    public int insertTNotice(TNotice tNotice)
    {
        tNotice.setCreateTime(DateUtils.getNowDate());
        return tNoticeMapper.insertTNotice(tNotice);
    }

    /**
     * 修改公告
     * 
     * @param tNotice 公告
     * @return 结果
     */
    @Override
    public int updateTNotice(TNotice tNotice)
    {
        tNotice.setUpdateTime(DateUtils.getNowDate());
        return tNoticeMapper.updateTNotice(tNotice);
    }

    /**
     * 批量删除公告
     * 
     * @param noticeIds 需要删除的公告主键
     * @return 结果
     */
    @Override
    public int deleteTNoticeByNoticeIds(Long[] noticeIds)
    {
        return tNoticeMapper.deleteTNoticeByNoticeIds(noticeIds);
    }

    /**
     * 删除公告信息
     * 
     * @param noticeId 公告主键
     * @return 结果
     */
    @Override
    public int deleteTNoticeByNoticeId(Long noticeId)
    {
        return tNoticeMapper.deleteTNoticeByNoticeId(noticeId);
    }

    @Override
    public List<TNotice> selectPublicNotices()
    {
        return tNoticeMapper.selectPublicNotices();
    }
}
