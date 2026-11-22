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
import com.ruoyi.system.domain.TActivity;
import com.ruoyi.system.service.ITActivityService;
import com.ruoyi.common.utils.poi.ExcelUtil;
import com.ruoyi.common.core.page.TableDataInfo;

/**
 * 第二课堂活动Controller
 * 
 * @author ruoyi
 * @date 2026-10-21
 */
@RestController
@RequestMapping("/system/activity")
public class TActivityController extends BaseController
{
    @Autowired
    private ITActivityService tActivityService;

    /**
     * 查询第二课堂活动列表
     */
    @PreAuthorize("@ss.hasPermi('system:activity:list')")
    @GetMapping("/list")
    public TableDataInfo list(TActivity tActivity)
    {
        startPage();
        List<TActivity> list = tActivityService.selectTActivityList(tActivity);
        return getDataTable(list);
    }

    /**
     * 主办单位（dept_label）下拉选项
     *
     * 2026-10-23 新增：原来前端部门下拉是自己捞一页活动在前端凑 distinct，
     * pageSize 不够（活动超 500 条）就漏项。这里给一条轻量接口，只返回去重名称数组：
     *   {"msg":"操作成功","code":200,"data":["师范学院","体育学院",...]}
     * 权限沿用 system:activity:list（能看到列表的人就能看到下拉）。
     */
    @PreAuthorize("@ss.hasPermi('system:activity:list')")
    @GetMapping("/deptOptions")
    public AjaxResult deptOptions()
    {
        return success(tActivityService.selectDeptOptions());
    }

    /**
     * 导出第二课堂活动列表
     */
    @PreAuthorize("@ss.hasPermi('system:activity:export')")
    @Log(title = "第二课堂活动", businessType = BusinessType.EXPORT)
    @PostMapping("/export")
    public void export(HttpServletResponse response, TActivity tActivity)
    {
        List<TActivity> list = tActivityService.selectTActivityList(tActivity);
        ExcelUtil<TActivity> util = new ExcelUtil<TActivity>(TActivity.class);
        util.exportExcel(response, list, "第二课堂活动数据");
    }

    /**
     * 获取第二课堂活动详细信息
     */
    @PreAuthorize("@ss.hasPermi('system:activity:query')")
    @GetMapping(value = "/{activityId}")
    public AjaxResult getInfo(@PathVariable("activityId") String activityId)
    {
        return success(tActivityService.selectTActivityByActivityId(activityId));
    }

    /**
     * 新增第二课堂活动
     */
    @PreAuthorize("@ss.hasPermi('system:activity:add')")
    @Log(title = "第二课堂活动", businessType = BusinessType.INSERT)
    @PostMapping
    public AjaxResult add(@RequestBody TActivity tActivity)
    {
        return toAjax(tActivityService.insertTActivity(tActivity));
    }

    /**
     * 修改第二课堂活动
     */
    @PreAuthorize("@ss.hasPermi('system:activity:edit')")
    @Log(title = "第二课堂活动", businessType = BusinessType.UPDATE)
    @PutMapping
    public AjaxResult edit(@RequestBody TActivity tActivity)
    {
        return toAjax(tActivityService.updateTActivity(tActivity));
    }

    /**
     * 删除第二课堂活动
     */
    @PreAuthorize("@ss.hasPermi('system:activity:remove')")
    @Log(title = "第二课堂活动", businessType = BusinessType.DELETE)
	@DeleteMapping("/{activityIds}")
    public AjaxResult remove(@PathVariable String[] activityIds)
    {
        return toAjax(tActivityService.deleteTActivityByActivityIds(activityIds));
    }
}
