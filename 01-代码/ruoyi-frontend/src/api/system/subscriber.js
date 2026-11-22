import request from '@/utils/request'

// 查询通知订阅者列表
export function listSubscriber(query) {
  return request({
    url: '/system/subscriber/list',
    method: 'get',
    params: query
  })
}

// 查询通知订阅者详细
export function getSubscriber(subscriberId) {
  return request({
    url: '/system/subscriber/' + subscriberId,
    method: 'get'
  })
}

// 新增通知订阅者
export function addSubscriber(data) {
  return request({
    url: '/system/subscriber',
    method: 'post',
    data: data
  })
}

// 修改通知订阅者
export function updateSubscriber(data) {
  return request({
    url: '/system/subscriber',
    method: 'put',
    data: data
  })
}

// 删除通知订阅者
export function delSubscriber(subscriberId) {
  return request({
    url: '/system/subscriber/' + subscriberId,
    method: 'delete'
  })
}
