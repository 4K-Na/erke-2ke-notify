package com.ruoyi.system.service.impl;

import java.util.List;
import com.ruoyi.common.utils.DateUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.ruoyi.system.mapper.TSubscriberMapper;
import com.ruoyi.system.domain.TSubscriber;
import com.ruoyi.system.service.ITSubscriberService;

/**
 * 通知订阅者Service业务层处理
 * 
 * @author ruoyi
 * @date 2026-10-21
 */
@Service
public class TSubscriberServiceImpl implements ITSubscriberService 
{
    @Autowired
    private TSubscriberMapper tSubscriberMapper;

    /**
     * 查询通知订阅者
     * 
     * @param subscriberId 通知订阅者主键
     * @return 通知订阅者
     */
    @Override
    public TSubscriber selectTSubscriberBySubscriberId(Long subscriberId)
    {
        return tSubscriberMapper.selectTSubscriberBySubscriberId(subscriberId);
    }

    /**
     * 查询通知订阅者列表
     * 
     * @param tSubscriber 通知订阅者
     * @return 通知订阅者
     */
    @Override
    public List<TSubscriber> selectTSubscriberList(TSubscriber tSubscriber)
    {
        return tSubscriberMapper.selectTSubscriberList(tSubscriber);
    }

    /**
     * 新增通知订阅者
     * 
     * @param tSubscriber 通知订阅者
     * @return 结果
     */
    @Override
    public int insertTSubscriber(TSubscriber tSubscriber)
    {
        tSubscriber.setCreateTime(DateUtils.getNowDate());
        return tSubscriberMapper.insertTSubscriber(tSubscriber);
    }

    /**
     * 修改通知订阅者
     * 
     * @param tSubscriber 通知订阅者
     * @return 结果
     */
    @Override
    public int updateTSubscriber(TSubscriber tSubscriber)
    {
        tSubscriber.setUpdateTime(DateUtils.getNowDate());
        return tSubscriberMapper.updateTSubscriber(tSubscriber);
    }

    /**
     * 批量删除通知订阅者
     * 
     * @param subscriberIds 需要删除的通知订阅者主键
     * @return 结果
     */
    @Override
    public int deleteTSubscriberBySubscriberIds(Long[] subscriberIds)
    {
        return tSubscriberMapper.deleteTSubscriberBySubscriberIds(subscriberIds);
    }

    /**
     * 删除通知订阅者信息
     * 
     * @param subscriberId 通知订阅者主键
     * @return 结果
     */
    @Override
    public int deleteTSubscriberBySubscriberId(Long subscriberId)
    {
        return tSubscriberMapper.deleteTSubscriberBySubscriberId(subscriberId);
    }
}
