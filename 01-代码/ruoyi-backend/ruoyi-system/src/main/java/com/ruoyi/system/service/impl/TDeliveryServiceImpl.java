package com.ruoyi.system.service.impl;

import java.util.List;
import com.ruoyi.common.utils.DateUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.ruoyi.system.mapper.TDeliveryMapper;
import com.ruoyi.system.domain.TDelivery;
import com.ruoyi.system.service.ITDeliveryService;

/**
 * 通知投递记录Service业务层处理
 * 
 * @author ruoyi
 * @date 2026-10-21
 */
@Service
public class TDeliveryServiceImpl implements ITDeliveryService 
{
    @Autowired
    private TDeliveryMapper tDeliveryMapper;

    /**
     * 查询通知投递记录
     * 
     * @param deliveryId 通知投递记录主键
     * @return 通知投递记录
     */
    @Override
    public TDelivery selectTDeliveryByDeliveryId(Long deliveryId)
    {
        return tDeliveryMapper.selectTDeliveryByDeliveryId(deliveryId);
    }

    /**
     * 查询通知投递记录列表
     * 
     * @param tDelivery 通知投递记录
     * @return 通知投递记录
     */
    @Override
    public List<TDelivery> selectTDeliveryList(TDelivery tDelivery)
    {
        return tDeliveryMapper.selectTDeliveryList(tDelivery);
    }

    // ==========================================================================
    // 【2026-10-23 审计 C §2.3（P1）处置：t_delivery 只读化】
    //
    // 下面 4 个写方法保留签名（ITDeliveryService 仍声明它们，删了会编译失败），
    // 但方法体一律 return 0，不再接触 TDeliveryMapper 的写方法
    // （Mapper 接口里的写方法声明已注释，对应 XML statement 也已整段注释）。
    // 返回值 0 在若依 toAjax 语义里 = 操作失败，前端会看到明确的失败提示。
    //
    // 分发器（Python）直接连 MySQL 写这张表，**不经过**本 Service，因此不受影响。
    // 唯一的合法写入口仍然只有 dispatcher.py 的 INSERT + IntegrityError 幂等逻辑。
    // ==========================================================================

    /**
     * 新增通知投递记录 —— 【已停用】t_delivery 是分发器幂等账本，禁止应用侧写入
     *
     * @param tDelivery 通知投递记录
     * @return 恒为 0（失败）
     */
    @Override
    public int insertTDelivery(TDelivery tDelivery)
    {
        return 0;
    }

    /**
     * 修改通知投递记录 —— 【已停用】改 send_status 会让失败重试永久丢失、统计口径失真
     *
     * @param tDelivery 通知投递记录
     * @return 恒为 0（失败）
     */
    @Override
    public int updateTDelivery(TDelivery tDelivery)
    {
        return 0;
    }

    /**
     * 批量删除通知投递记录 —— 【已停用】删已 sent 行会让分发器下一轮重复推送
     *
     * @param deliveryIds 需要删除的通知投递记录主键
     * @return 恒为 0（失败）
     */
    @Override
    public int deleteTDeliveryByDeliveryIds(Long[] deliveryIds)
    {
        return 0;
    }

    /**
     * 删除通知投递记录信息 —— 【已停用】同上
     *
     * @param deliveryId 通知投递记录主键
     * @return 恒为 0（失败）
     */
    @Override
    public int deleteTDeliveryByDeliveryId(Long deliveryId)
    {
        return 0;
    }

    /**
     * 按活动聚合统计投递情况
     */
    @Override
    public java.util.List<java.util.Map<String, Object>> selectDeliverySummary(TDelivery tDelivery)
    {
        return tDeliveryMapper.selectDeliverySummary(tDelivery);
    }

}
