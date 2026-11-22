import request from '@/utils/request'

// 查询第二课堂活动列表
export function listActivity(query) {
  return request({
    url: '/system/activity/list',
    method: 'get',
    params: query
  })
}

// 查询第二课堂活动详细
export function getActivity(activityId) {
  return request({
    url: '/system/activity/' + activityId,
    method: 'get'
  })
}

// 新增第二课堂活动
export function addActivity(data) {
  return request({
    url: '/system/activity',
    method: 'post',
    data: data
  })
}

// 修改第二课堂活动
export function updateActivity(data) {
  return request({
    url: '/system/activity',
    method: 'put',
    data: data
  })
}

// 主办学院下拉选项（后端去重返回）
export function deptOptions() {
  return request({
    url: '/system/activity/deptOptions',
    method: 'get'
  })
}

// 删除第二课堂活动
export function delActivity(activityId) {
  return request({
    url: '/system/activity/' + activityId,
    method: 'delete'
  })
}
