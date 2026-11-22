package com.ruoyi.system.mapper;

import java.util.List;
import com.ruoyi.system.domain.TSubscriber;

/**
 * 通知订阅者Mapper接口
 * 
 * @author ruoyi
 * @date 2026-10-21
 */
public interface TSubscriberMapper 
{
    /**
     * 查询通知订阅者
     * 
     * @param subscriberId 通知订阅者主键
     * @return 通知订阅者
     */
    public TSubscriber selectTSubscriberBySubscriberId(Long subscriberId);

    /**
     * 查询通知订阅者列表
     * 
     * @param tSubscriber 通知订阅者
     * @return 通知订阅者集合
     */
    public List<TSubscriber> selectTSubscriberList(TSubscriber tSubscriber);

    /**
     * 新增通知订阅者
     * 
     * @param tSubscriber 通知订阅者
     * @return 结果
     */
    public int insertTSubscriber(TSubscriber tSubscriber);

    /**
     * 修改通知订阅者
     * 
     * @param tSubscriber 通知订阅者
     * @return 结果
     */
    public int updateTSubscriber(TSubscriber tSubscriber);

    /**
     * 删除通知订阅者
     * 
     * @param subscriberId 通知订阅者主键
     * @return 结果
     */
    public int deleteTSubscriberBySubscriberId(Long subscriberId);

    /**
     * 批量删除通知订阅者
     * 
     * @param subscriberIds 需要删除的数据主键集合
     * @return 结果
     */
    public int deleteTSubscriberBySubscriberIds(Long[] subscriberIds);
}
