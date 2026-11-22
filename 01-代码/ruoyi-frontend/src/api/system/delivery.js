import request from '@/utils/request'

// 查询通知投递记录列表
export function listDelivery(query) {
  return request({
    url: '/system/delivery/list',
    method: 'get',
    params: query
  })
}

// 查询通知投递记录详细
// 按活动聚合的投递概览
export function summaryDelivery(query) {
  return request({
    url: '/system/delivery/summary',
    method: 'get',
    params: query
  })
}

export function getDelivery(deliveryId) {
  return request({
    url: '/system/delivery/' + deliveryId,
    method: 'get'
  })
}

// 新增通知投递记录
export function addDelivery(data) {
  return request({
    url: '/system/delivery',
    method: 'post',
    data: data
  })
}

// 修改通知投递记录
export function updateDelivery(data) {
  return request({
    url: '/system/delivery',
    method: 'put',
    data: data
  })
}

// 删除通知投递记录
export function delDelivery(deliveryId) {
  return request({
    url: '/system/delivery/' + deliveryId,
    method: 'delete'
  })
}
