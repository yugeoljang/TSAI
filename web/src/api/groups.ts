import { http } from './http'
import type {
  ApiGroup,
  ApiGroupCreate,
  ApiGroupDetail,
  ApiGroupMember,
  ApiGroupMemberCreate,
  ApiGroupMemberUpdate,
  ApiGroupUpdate,
} from '@/types/api'

const A = '/api/admin'

export const listGroups = () => http.get<ApiGroup[]>(`${A}/groups`).then((r) => r.data)

/** 唯一会返回 members 的接口 —— 列表接口不带成员 */
export const getGroup = (id: string) => http.get<ApiGroupDetail>(`${A}/groups/${id}`).then((r) => r.data)

export const createGroup = (input: ApiGroupCreate) =>
  http.post<ApiGroup>(`${A}/groups`, input).then((r) => r.data)

export const updateGroup = (id: string, input: ApiGroupUpdate) =>
  http.patch<ApiGroup>(`${A}/groups/${id}`, input).then((r) => r.data)

export const deleteGroup = (id: string) => http.delete<void>(`${A}/groups/${id}`)

export const addMember = (groupId: string, input: ApiGroupMemberCreate) =>
  http.post<ApiGroupMember>(`${A}/groups/${groupId}/members`, input).then((r) => r.data)

export const updateMember = (groupId: string, memberId: string, input: ApiGroupMemberUpdate) =>
  http.patch<ApiGroupMember>(`${A}/groups/${groupId}/members/${memberId}`, input).then((r) => r.data)

export const removeMember = (groupId: string, memberId: string) =>
  http.delete<void>(`${A}/groups/${groupId}/members/${memberId}`)

/** 返回重排后的成员数组，调用方应直接用它重渲染，而不是本地臆测顺序 */
export const reorderMembers = (groupId: string, orderedMemberIds: string[]) =>
  http
    .put<ApiGroupMember[]>(`${A}/groups/${groupId}/members/order`, { orderedMemberIds })
    .then((r) => r.data)
