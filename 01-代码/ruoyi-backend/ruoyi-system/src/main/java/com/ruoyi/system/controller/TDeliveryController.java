package com.ruoyi.system.controller;

import java.util.List;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import com.ruoyi.common.annotation.Log;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.enums.BusinessType;
import com.ruoyi.system.domain.TDelivery;
import com.ruoyi.system.service.ITDeliveryService;
import com.ruoyi.common.utils.poi.ExcelUtil;
import com.ruoyi.common.core.page.TableDataInfo;

/**
 * 通知投递记录Controller
 * 
 * @author ruoyi
 * @date 2026-10-21
 */
@RestController
@RequestMapping("/system/delivery")
public class TDeliveryController extends BaseController
{
    @Autowired
    private ITDeliveryService tDeliveryService;

    /**
     * 查询通知投递记录列表
     */
    @PreAuthorize("@ss.hasPermi('system:delivery:list')")
    @GetMapping("/list")
    public TableDataInfo list(TDelivery tDelivery)
    {
        startPage();
        List<TDelivery> list = tDeliveryService.selectTDeliveryList(tDelivery);
        return getDataTable(list);
    }

    /**
     * 导出通知投递记录列表
     */
    /**
     * 按活动聚合的投递概览（一行一个活动，失败优先）
     */
    @PreAuthorize("@ss.hasPermi('system:delivery:list')")
    @GetMapping("/summary")
    public TableDataInfo summary(TDelivery tDelivery)
    {
        startPage();
        java.util.List<java.util.Map<String, Object>> list = tDeliveryService.selectDeliverySummary(tDelivery);
        return getDataTable(list);
    }

    @PreAuthorize("@ss.hasPermi('system:delivery:export')")
    @Log(title = "通知投递记录", businessType = BusinessType.EXPORT)
    @PostMapping("/export")
    public void export(HttpServletResponse response, TDelivery tDelivery)
    {
        List<TDelivery> list = tDeliveryService.selectTDeliveryList(tDelivery);
        ExcelUtil<TDelivery> util = new ExcelUtil<TDelivery>(TDelivery.class);
        util.exportExcel(response, list, "通知投递记录数据");
    }

    /**
     * 获取通知投递记录详细信息
     */
    @PreAuthorize("@ss.hasPermi('system:delivery:query')")
    @GetMapping(value = "/{deliveryId}")
    public AjaxResult getInfo(@PathVariable("deliveryId") Long deliveryId)
    {
        return success(tDeliveryService.selectTDeliveryByDeliveryId(deliveryId));
    }

    /**
     * 新增通知投递记录 —— 【已禁用，只读】
     *
     * 审计 C §2.3（P1）：t_delivery 不是业务表，它是分发器
     * （/opt/2ke-hub/dispatcher.py）的**幂等去重账本**。分发器靠
     * INSERT 是否撞 UNIQUE(activity_id, subscriber_id) 决定「这一轮发不发」：
     *
     *   n = INSERT ... ; except IntegrityError: n = 0
     *   只有 n == 1 才真正调用企业微信发送
     *
     * 因此后台手工插一条 = 分发器下一轮插入 n=0 = **该学生永久收不到这条活动**，
     * 而列表里显示得像一条正常记录，事后无从察觉。
     *
     * 处置（2026-10-23）：add / edit / remove 三个写接口改为直接返回错误，
     * 保留映射让前端拿到明确提示而不是 404；同时 TDeliveryMapper.xml 里
     * 对应的 insert/update/delete statement 已整段注释，双保险。
     * list / summary / getInfo / export 保持可用（只读）。
     */
    @PreAuthorize("@ss.hasPermi('system:delivery:add')")
    @Log(title = "通知投递记录-拒绝手工新增", businessType = BusinessType.INSERT)
    @PostMapping
    public AjaxResult add(@RequestBody TDelivery tDelivery)
    {
        return AjaxResult.error("通知投递记录为系统自动写入，禁止手工修改");
    }

    /**
     * 修改通知投递记录 —— 【已禁用，只读】
     *
     * 审计 C §2.3（P1）：把 send_status 从 failed 改成 sent 会让失败重试永久丢失，
     * 并把首页统计口径污染成「全部成功」。
     * 真有重发需求请另开语义明确的 POST /system/delivery/retry（把 failed 置 pending），
     * 不要改账本本身。
     */
    @PreAuthorize("@ss.hasPermi('system:delivery:edit')")
    @Log(title = "通知投递记录-拒绝手工修改", businessType = BusinessType.UPDATE)
    @PutMapping
    public AjaxResult edit(@RequestBody TDelivery tDelivery)
    {
        return AjaxResult.error("通知投递记录为系统自动写入，禁止手工修改");
    }

    /**
     * 删除通知投递记录 —— 【已禁用，只读】
     *
     * 审计 C §2.3（P1）：当前 219 行全部是真实发送成功的账本，删一行 =
     * 分发器下一轮重新插入成功 = **同一活动给学生重复推一次**（骚扰 + 掉信任）。
     */
    @PreAuthorize("@ss.hasPermi('system:delivery:remove')")
    @Log(title = "通知投递记录-拒绝手工删除", businessType = BusinessType.DELETE)
    @DeleteMapping("/{deliveryIds}")
    public AjaxResult remove(@PathVariable Long[] deliveryIds)
    {
        return AjaxResult.error("通知投递记录为系统自动写入，禁止手工删除");
    }
}
