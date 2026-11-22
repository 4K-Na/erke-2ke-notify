package com.ruoyi.system.service.impl;

import java.util.List;
import com.ruoyi.common.utils.DateUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.ruoyi.system.mapper.TActivityMapper;
import com.ruoyi.system.domain.TActivity;
import com.ruoyi.system.service.ITActivityService;

/**
 * 第二课堂活动Service业务层处理
 * 
 * @author ruoyi
 * @date 2026-10-21
 */
@Service
public class TActivityServiceImpl implements ITActivityService 
{
    @Autowired
    private TActivityMapper tActivityMapper;

    /**
     * 查询第二课堂活动
     * 
     * @param activityId 第二课堂活动主键
     * @return 第二课堂活动
     */
    @Override
    public TActivity selectTActivityByActivityId(String activityId)
    {
        return tActivityMapper.selectTActivityByActivityId(activityId);
    }

    /**
     * 查询第二课堂活动列表
     * 
     * @param tActivity 第二课堂活动
     * @return 第二课堂活动
     */
    @Override
    public List<TActivity> selectTActivityList(TActivity tActivity)
    {
        return tActivityMapper.selectTActivityList(tActivity);
    }

    /**
     * 查询去重后的主办单位（dept_label）列表，给后台下拉用
     */
    @Override
    public List<String> selectDeptOptions()
    {
        return tActivityMapper.selectDeptOptions();
    }

    /**
     * 新增第二课堂活动
     * 
     * @param tActivity 第二课堂活动
     * @return 结果
     */
    @Override
    public int insertTActivity(TActivity tActivity)
    {
        tActivity.setCreateTime(DateUtils.getNowDate());
        return tActivityMapper.insertTActivity(tActivity);
    }

    /**
     * 修改第二课堂活动
     * 
     * @param tActivity 第二课堂活动
     * @return 结果
     */
    @Override
    public int updateTActivity(TActivity tActivity)
    {
        tActivity.setUpdateTime(DateUtils.getNowDate());
        return tActivityMapper.updateTActivity(tActivity);
    }

    /**
     * 批量删除第二课堂活动
     * 
     * @param activityIds 需要删除的第二课堂活动主键
     * @return 结果
     */
    @Override
    public int deleteTActivityByActivityIds(String[] activityIds)
    {
        return tActivityMapper.deleteTActivityByActivityIds(activityIds);
    }

    /**
     * 删除第二课堂活动信息
     * 
     * @param activityId 第二课堂活动主键
     * @return 结果
     */
    @Override
    public int deleteTActivityByActivityId(String activityId)
    {
        return tActivityMapper.deleteTActivityByActivityId(activityId);
    }
}
