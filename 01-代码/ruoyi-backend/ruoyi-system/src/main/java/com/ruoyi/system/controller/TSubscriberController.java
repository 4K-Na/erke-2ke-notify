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
import com.ruoyi.system.domain.TSubscriber;
import com.ruoyi.system.service.ITSubscriberService;
import com.ruoyi.common.utils.poi.ExcelUtil;
import com.ruoyi.common.core.page.TableDataInfo;

/**
 * 通知订阅者Controller
 * 
 * @author ruoyi
 * @date 2026-10-21
 */
@RestController
@RequestMapping("/system/subscriber")
public class TSubscriberController extends BaseController
{
    @Autowired
    private ITSubscriberService tSubscriberService;

    /**
     * 查询通知订阅者列表
     */
    @PreAuthorize("@ss.hasPermi('system:subscriber:list')")
    @GetMapping("/list")
    public TableDataInfo list(TSubscriber tSubscriber)
    {
        startPage();
        List<TSubscriber> list = tSubscriberService.selectTSubscriberList(tSubscriber);
        return getDataTable(list);
    }

    /**
     * 导出通知订阅者列表
     */
    @PreAuthorize("@ss.hasPermi('system:subscriber:export')")
    @Log(title = "通知订阅者", businessType = BusinessType.EXPORT)
    @PostMapping("/export")
    public void export(HttpServletResponse response, TSubscriber tSubscriber)
    {
        List<TSubscriber> list = tSubscriberService.selectTSubscriberList(tSubscriber);
        ExcelUtil<TSubscriber> util = new ExcelUtil<TSubscriber>(TSubscriber.class);
        util.exportExcel(response, list, "通知订阅者数据");
    }

    /**
     * 获取通知订阅者详细信息
     */
    @PreAuthorize("@ss.hasPermi('system:subscriber:query')")
    @GetMapping(value = "/{subscriberId}")
    public AjaxResult getInfo(@PathVariable("subscriberId") Long subscriberId)
    {
        return success(tSubscriberService.selectTSubscriberBySubscriberId(subscriberId));
    }

    /**
     * 新增通知订阅者
     */
    @PreAuthorize("@ss.hasPermi('system:subscriber:add')")
    @Log(title = "通知订阅者", businessType = BusinessType.INSERT)
    @PostMapping
    public AjaxResult add(@RequestBody TSubscriber tSubscriber)
    {
        return toAjax(tSubscriberService.insertTSubscriber(tSubscriber));
    }

    /**
     * 修改通知订阅者
     */
    @PreAuthorize("@ss.hasPermi('system:subscriber:edit')")
    @Log(title = "通知订阅者", businessType = BusinessType.UPDATE)
    @PutMapping
    public AjaxResult edit(@RequestBody TSubscriber tSubscriber)
    {
        return toAjax(tSubscriberService.updateTSubscriber(tSubscriber));
    }

    /**
     * 删除通知订阅者
     */
    @PreAuthorize("@ss.hasPermi('system:subscriber:remove')")
    @Log(title = "通知订阅者", businessType = BusinessType.DELETE)
	@DeleteMapping("/{subscriberIds}")
    public AjaxResult remove(@PathVariable Long[] subscriberIds)
    {
        return toAjax(tSubscriberService.deleteTSubscriberBySubscriberIds(subscriberIds));
    }
}
