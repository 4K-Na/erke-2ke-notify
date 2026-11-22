package com.ruoyi.system.mapper;

import java.util.List;
import com.ruoyi.system.domain.TActivity;

/**
 * 第二课堂活动Mapper接口
 * 
 * @author ruoyi
 * @date 2026-10-21
 */
public interface TActivityMapper 
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
     * 2026-10-23 新增：原来前端部门下拉是自己捞一页活动在前端凑 distinct，
     * pageSize 一旦不够（活动超 500 条）就会漏项。改为后端一条轻量 distinct。
     *
     * @return 主办单位名称集合（已去重、已排序、已排除空值）
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
     * 删除第二课堂活动
     * 
     * @param activityId 第二课堂活动主键
     * @return 结果
     */
    public int deleteTActivityByActivityId(String activityId);

    /**
     * 批量删除第二课堂活动
     * 
     * @param activityIds 需要删除的数据主键集合
     * @return 结果
     */
    public int deleteTActivityByActivityIds(String[] activityIds);
}
