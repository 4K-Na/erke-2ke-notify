package com.ruoyi.system.service;

import java.util.List;
import com.ruoyi.system.domain.TActivity;

/**
 * 第二课堂活动Service接口
 * 
 * @author ruoyi
 * @date 2026-10-21
 */
public interface ITActivityService 
{
    /**
     * 查询第二课堂活动
     * 
     * @param activityId 第二课堂活动主键
     * @return 第二课堂活动
     */
    public TActivity selectTActivityByActivityId(String activityId);

    /**
     * 查询第二课堂活动列表
     * 
     * @param tActivity 第二课堂活动
     * @return 第二课堂活动集合
     */
    public List<TActivity> selectTActivityList(TActivity tActivity);

    /**
     * 查询去重后的主办单位（dept_label）列表，给后台下拉用
     *
     * @return 主办单位名称集合
     */
    public List<String> selectDeptOptions();

    /**
     * 新增第二课堂活动
     * 
     * @param tActivity 第二课堂活动
     * @return 结果
     */
    public int insertTActivity(TActivity tActivity);

    /**
     * 修改第二课堂活动
     * 
     * @param tActivity 第二课堂活动
     * @return 结果
     */
    public int updateTActivity(TActivity tActivity);

    /**
     * 批量删除第二课堂活动
     * 
     * @param activityIds 需要删除的第二课堂活动主键集合
     * @return 结果
     */
    public int deleteTActivityByActivityIds(String[] activityIds);

    /**
     * 删除第二课堂活动信息
     * 
     * @param activityId 第二课堂活动主键
     * @return 结果
     */
    public int deleteTActivityByActivityId(String activityId);
}
