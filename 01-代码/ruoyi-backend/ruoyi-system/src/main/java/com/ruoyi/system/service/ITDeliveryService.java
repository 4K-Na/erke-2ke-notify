package com.ruoyi.system.service;

import java.util.List;
import com.ruoyi.system.domain.TDelivery;

/**
 * 通知投递记录Service接口
 * 
 * @author ruoyi
 * @date 2026-10-21
 */
public interface ITDeliveryService 
{
    /**
     * 查询通知投递记录
     * 
     * @param deliveryId 通知投递记录主键
     * @return 通知投递记录
     */
    public TDelivery selectTDeliveryByDeliveryId(Long deliveryId);

    /**
     * 查询通知投递记录列表
     * 
     * @param tDelivery 通知投递记录
     * @return 通知投递记录集合
     */
    public List<TDelivery> selectTDeliveryList(TDelivery tDelivery);
    /**
     * 按活动聚合统计投递情况
     *
     * @param tDelivery 查询条件
     * @return 聚合结果
     */
    public java.util.List<java.util.Map<String, Object>> selectDeliverySummary(TDelivery tDelivery);


    /**
     * 新增通知投递记录
     * 
     * @param tDelivery 通知投递记录
     * @return 结果
     */
    public int insertTDelivery(TDelivery tDelivery);

    /**
     * 修改通知投递记录
     * 
     * @param tDelivery 通知投递记录
     * @return 结果
     */
    public int updateTDelivery(TDelivery tDelivery);

    /**
     * 批量删除通知投递记录
     * 
     * @param deliveryIds 需要删除的通知投递记录主键集合
     * @return 结果
     */
    public int deleteTDeliveryByDeliveryIds(Long[] deliveryIds);

    /**
     * 删除通知投递记录信息
     * 
     * @param deliveryId 通知投递记录主键
     * @return 结果
     */
    public int deleteTDeliveryByDeliveryId(Long deliveryId);
}
