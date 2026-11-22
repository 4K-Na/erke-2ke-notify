package com.ruoyi.system.mapper;

import java.util.List;
import com.ruoyi.system.domain.TDelivery;

/**
 * 通知投递记录Mapper接口
 * 
 * @author ruoyi
 * @date 2026-10-21
 */
public interface TDeliveryMapper 
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
     * 按活动聚合统计投递情况（一行一个活动）
     *
     * @param tDelivery 查询条件
     * @return 聚合结果
     */
    public java.util.List<java.util.Map<String, Object>> selectDeliverySummary(TDelivery tDelivery);


    // ==========================================================================
    // 【2026-10-23 审计 C §2.3（P1）处置：写方法整体停用】
    //
    // t_delivery 是分发器 /opt/2ke-hub/dispatcher.py 的幂等去重账本，
    // 不是可编辑的业务表。后台写它会直接造成「漏推」或「重推」。
    //
    // 保留接口声明（不删，避免别处引用直接编译失败）会诱导后续有人再调用，
    // 因此这里连同 TDeliveryMapper.xml 里的 4 个 statement 一起注释停用：
    //   - 语句级：XML 里已整段注释，即使被调用也只会抛 BindingException，
    //     绝不会产生一条 SQL 打到 t_delivery。
    //   - 代码级：TDeliveryServiceImpl 的 insert/update/delete 已改为直接 return 0，
    //     不再引用本接口的写方法，故本段注释不影响编译。
    //
    // 恢复方式：反向操作 —— 取消本段与 TDeliveryMapper.xml 对应段落注释，
    // 并恢复 TDeliveryServiceImpl / TDeliveryController 的原始实现
    // （原件在 /root/pre-fix-backup-20261023-125822/ruoyi-src-*/ 下）。
    //
    // public int insertTDelivery(TDelivery tDelivery);
    //
    // public int updateTDelivery(TDelivery tDelivery);
    //
    // public int deleteTDeliveryByDeliveryId(Long deliveryId);
    //
    // public int deleteTDeliveryByDeliveryIds(Long[] deliveryIds);
    // ==========================================================================
}
