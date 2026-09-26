<template>
  <section class="page" data-module="box-inventory">
    <header class="page-head">
      <div>
        <h2>站点盘点</h2>
        <p class="page-desc">按归属站点盘点在外温控箱体；温控范围逐箱取自箱体台账，不在本页另存，因此与箱体台账必然一致。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="reload">刷新盘点</button>
      </div>
    </header>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">站点（含在库）</span>
        <strong class="stat-value">{{ groups.length }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">在外箱体（使用中）</span>
        <strong class="stat-value">{{ totalUsing }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">保温材料受损</span>
        <strong class="stat-value">{{ totalDamaged }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">已报废</span>
        <strong class="stat-value">{{ totalScrap }}</strong>
      </article>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th style="width: 36px"></th>
          <th>归属站点</th>
          <th>箱体数量</th>
          <th>使用中</th>
          <th>清洗中</th>
          <th>可用</th>
          <th>报废</th>
          <th>保温材料受损</th>
          <th>温控范围（与台账同源）</th>
          <th style="width: 120px">操作</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="(group, index) in groups" :key="group['归属站点']">
          <tr>
            <td><button class="link station-expand" type="button" @click="toggle(index)">{{ expanded[index] ? '收起' : '展开' }}</button></td>
            <td><strong>{{ group['归属站点'] }}</strong></td>
            <td>{{ group['箱体数量'] }}</td>
            <td>{{ group['使用中'] }}</td>
            <td>{{ group['清洗中'] }}</td>
            <td>{{ group['可用'] }}</td>
            <td>{{ group['报废'] }}</td>
            <td><span v-if="group['保温材料受损']" class="tag damage">{{ group['保温材料受损'] }}</span><span v-else>0</span></td>
            <td>{{ group['温控范围汇总'].join('、') || '—' }}</td>
            <td><button class="btn small" type="button" @click="viewRecord(group)">出入库记录</button></td>
          </tr>
          <tr v-if="expanded[index]">
            <td></td>
            <td colspan="9">
              <table class="detail-table">
                <thead>
                  <tr><th>箱体编号</th><th>箱体类型</th><th>温控范围</th><th>箱体状态</th><th>保温材料</th><th>最近记录编号</th></tr>
                </thead>
                <tbody>
                  <tr v-for="box in group['明细']" :key="box['箱体编号']">
                    <td>{{ box['箱体编号'] }}</td>
                    <td>{{ box['箱体类型'] }}</td>
                    <td>{{ box['温控范围'] }}</td>
                    <td><span :class="['tag', statusClass(box['箱体状态'])]">{{ box['箱体状态'] }}</span></td>
                    <td>
                      <span v-if="box['保温材料状态'] === '受损'" class="tag damage">受损</span>
                      <span v-else class="tag ok">正常</span>
                    </td>
                    <td>{{ box['最近记录编号'] || '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </td>
          </tr>
        </template>
        <tr v-if="!groups.length">
          <td colspan="10" class="empty-state">暂无盘点数据</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 记录弹窗：复用 /api/box/records，点站点时用该站点下任一箱体编号检索不到跨站点记录，
         因此弹窗内按该站点全部箱体编号逐条拉取 /records/by-box 后合并去重。 -->
    <div v-if="recordModal.open" class="modal-mask" @click.self="recordModal.open = false">
      <div class="modal wide">
        <div class="modal-head">
          <h3>出入库记录 · {{ recordModal.station }}</h3>
          <button class="modal-close" type="button" @click="recordModal.open = false">×</button>
        </div>
        <div class="modal-body">
          <table class="data-table">
            <thead>
              <tr><th>记录编号</th><th>类型</th><th>箱体类型</th><th>温控范围</th><th>数量</th><th>箱体编号</th><th>出库日期</th><th>回收日期</th></tr>
            </thead>
            <tbody>
              <tr v-for="rec in recordModal.items" :key="rec['记录编号']">
                <td>{{ rec['记录编号'] }}</td>
                <td>{{ rec['记录类型'] }}</td>
                <td>{{ rec['箱体类型'] }}</td>
                <td>{{ rec['温控范围'] }}</td>
                <td>{{ rec['数量'] }}</td>
                <td>{{ rec['箱体编号'].join('、') }}</td>
                <td>{{ rec['出库日期'] || '—' }}</td>
                <td>{{ rec['回收日期'] || '—' }}</td>
              </tr>
              <tr v-if="!recordModal.items.length">
                <td colspan="8" class="empty-state">该站点暂无出入库记录</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type DetailBox = {
  箱体编号: string
  箱体类型: string
  温控范围: string
  保温材料状态: string
  箱体状态: string
  最近记录编号: string
}
type StationGroup = {
  归属站点: string
  箱体数量: number
  使用中: number
  清洗中: number
  可用: number
  报废: number
  保温材料受损: number
  温控范围汇总: string[]
  明细: DetailBox[]
}
type BoxRecord = {
  记录编号: string
  记录类型: string
  箱体类型: string
  温控范围: string
  数量: number
  箱体编号: string[]
  出库日期: string
  回收日期: string
}

const ENDPOINT = '/api/box'
const groups = ref<StationGroup[]>([])
const expanded = reactive<Record<number, boolean>>({})
const errorMessage = ref('')

const totalUsing = computed(() => groups.value.reduce((sum, g) => sum + g.使用中, 0))
const totalDamaged = computed(() => groups.value.reduce((sum, g) => sum + g.保温材料受损, 0))
const totalScrap = computed(() => groups.value.reduce((sum, g) => sum + g.报废, 0))

function statusClass(status: string): string {
  return { 可用: 'avail', 使用中: 'using', 清洗中: 'wash', 报废: 'scrap' }[status] ?? ''
}

function toggle(index: number) {
  expanded[index] = !expanded[index]
}

const recordModal = reactive<{ open: boolean; station: string; items: BoxRecord[] }>({
  open: false,
  station: '',
  items: [],
})

async function viewRecord(group: StationGroup) {
  recordModal.station = group.归属站点
  recordModal.items = []
  recordModal.open = true
  try {
    // 记录挂在箱体编号下：逐箱查询后按记录编号合并去重，最新在前。
    const collected = new Map<string, BoxRecord>()
    for (const box of group.明细) {
      const response = await request(`${ENDPOINT}/records/by-box/${encodeURIComponent(box.箱体编号)}`)
      if (!response.ok) {
        continue
      }
      const payload = (await response.json()) as { items: BoxRecord[] }
      for (const rec of payload.items) {
        collected.set(rec.记录编号, rec)
      }
    }
    recordModal.items = [...collected.values()].sort((a, b) => b.记录编号.localeCompare(a.记录编号))
  } catch {
    errorMessage.value = '出入库记录读取失败'
  }
}

async function reload() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/station-inventory`)
    if (!response.ok) {
      throw new Error('站点盘点数据读取失败')
    }
    const payload = (await response.json()) as { items: StationGroup[] }
    groups.value = payload.items ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '站点盘点数据读取失败'
  }
}

onMounted(reload)
</script>
