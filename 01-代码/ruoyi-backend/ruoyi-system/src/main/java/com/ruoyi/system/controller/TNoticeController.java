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
import com.ruoyi.common.annotation.Anonymous;
import com.ruoyi.common.annotation.Log;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.enums.BusinessType;
import com.ruoyi.system.domain.TNotice;
import com.ruoyi.system.service.ITNoticeService;
import com.ruoyi.common.utils.poi.ExcelUtil;
import com.ruoyi.common.core.page.TableDataInfo;

/**
 * 公告Controller
 * 
 * @author ruoyi
 * @date 2026-10-21
 */
@RestController
@RequestMapping("/system/tnotice")
public class TNoticeController extends BaseController
{
    @Autowired
    private ITNoticeService tNoticeService;

    /**
     * 查询公告列表
     */
    @PreAuthorize("@ss.hasPermi('system:notice:list')")
    @GetMapping("/list")
    public TableDataInfo list(TNotice tNotice)
    {
        startPage();
        List<TNotice> list = tNoticeService.selectTNoticeList(tNotice);
        return getDataTable(list);
    }

    /**
     * 导出公告列表
     */
    @PreAuthorize("@ss.hasPermi('system:notice:export')")
    @Log(title = "公告", businessType = BusinessType.EXPORT)
    @PostMapping("/export")
    public void export(HttpServletResponse response, TNotice tNotice)
    {
        List<TNotice> list = tNoticeService.selectTNoticeList(tNotice);
        ExcelUtil<TNotice> util = new ExcelUtil<TNotice>(TNotice.class);
        util.exportExcel(response, list, "公告数据");
    }

    /**
     * 获取公告详细信息
     */
    @PreAuthorize("@ss.hasPermi('system:notice:query')")
    @GetMapping(value = "/{noticeId}")
    public AjaxResult getInfo(@PathVariable("noticeId") Long noticeId)
    {
        return success(tNoticeService.selectTNoticeByNoticeId(noticeId));
    }

    /**
     * 新增公告
     */
    @PreAuthorize("@ss.hasPermi('system:notice:add')")
    @Log(title = "公告", businessType = BusinessType.INSERT)
    @PostMapping
    public AjaxResult add(@RequestBody TNotice tNotice)
    {
        return toAjax(tNoticeService.insertTNotice(tNotice));
    }

    /**
     * 修改公告
     */
    @PreAuthorize("@ss.hasPermi('system:notice:edit')")
    @Log(title = "公告", businessType = BusinessType.UPDATE)
    @PutMapping
    public AjaxResult edit(@RequestBody TNotice tNotice)
    {
        return toAjax(tNoticeService.updateTNotice(tNotice));
    }

    /**
     * 删除公告
     */
    @PreAuthorize("@ss.hasPermi('system:notice:remove')")
    @Log(title = "公告", businessType = BusinessType.DELETE)
	@DeleteMapping("/{noticeIds}")
    public AjaxResult remove(@PathVariable Long[] noticeIds)
    {
        return toAjax(tNoticeService.deleteTNoticeByNoticeIds(noticeIds));
    }

    /**
     * 公开接口：公告页用，不需要登录。
     * 只返回「状态正常 + 在有效期内」的公告，按置顶和排序号排。
     */
    @Anonymous
    @GetMapping("/public/list")
    public AjaxResult publicList()
    {
        List<TNotice> list = tNoticeService.selectPublicNotices();
        return success(list);
    }
}
