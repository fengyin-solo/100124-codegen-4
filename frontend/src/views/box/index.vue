<template>
  <section class="page" data-module="box">
    <header class="page-head">
      <div>
        <h2>温控箱体管理</h2>
        <p class="page-desc">维护温控箱体台账，支持批量出库、批量回收与站点盘点；出库记录挂在箱体编号下，不同箱体类型自动拆分出库单。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记温控箱体</button>
        <button class="btn" type="button" @click="exportRows">导出温控箱体清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <nav class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-item"
        :class="{ active: activeTab === tab.key }"
        type="button"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </nav>

    <template v-if="activeTab === 'ledger'">
      <form class="filter-bar" @submit.prevent="reload">
        <label class="filter-item">
          <span>箱体编号</span>
          <input v-model="keyword" placeholder="按箱体编号检索" />
        </label>
        <label class="filter-item">
          <span>箱体状态</span>
          <select v-model="statusFilter">
            <option value="">全部状态</option>
            <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
          </select>
        </label>
        <button class="btn" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
      </form>

      <div class="batch-bar">
        <span>已勾选 {{ selectedIds.length }} 台</span>
        <button class="btn primary" type="button" :disabled="!selectedIds.length" @click="openCheckout">批量出库</button>
        <button class="btn" type="button" :disabled="!selectedIds.length" @click="runBatchRecycle">批量回收</button>
        <span class="batch-tip">批量出库按箱体类型自动拆分出库单；回收时受损、报废箱体会被单独挑出</span>
      </div>

      <table class="data-table">
        <thead>
          <tr>
            <th>
              <input
                type="checkbox"
                :checked="allVisibleSelected"
                @change="toggleSelectAll"
              />
            </th>
            <th v-for="column in columns" :key="column">{{ column }}</th>
            <th>可执行动作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="String(row.id)">
            <td>
              <input
                type="checkbox"
                :checked="selectedIds.includes(Number(row.id))"
                @change="toggleSelect(Number(row.id))"
              />
            </td>
            <td v-for="column in columns" :key="column">{{ row[column] || '—' }}</td>
            <td class="row-actions">
              <button
                v-for="action in actions"
                :key="action"
                class="link"
                type="button"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
              <button class="link" type="button" @click="viewBoxRecords(row)">出库记录</button>
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td :colspan="columns.length + 2" class="empty-state">暂无温控箱体数据，可先登记温控箱体</td>
          </tr>
        </tbody>
      </table>
    </template>

    <template v-else-if="activeTab === 'station'">
      <p class="page-desc">站点盘点：按归属站点分组，温控范围与箱体台账同源，不会出现两边对不上。</p>
      <div class="station-grid">
        <article v-for="group in stationGroups" :key="group.归属站点" class="station-card">
          <header>
            <strong>{{ group.归属站点 }}</strong>
            <span>在场 {{ group.数量 }} 台</span>
          </header>
          <table class="data-table">
            <thead>
              <tr>
                <th>箱体编号</th>
                <th>箱体类型</th>
                <th>温控范围</th>
                <th>出库日期</th>
                <th>箱体状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="box in group.箱体列表" :key="box.箱体编号">
                <td>{{ box.箱体编号 }}</td>
                <td>{{ box.箱体类型 }}</td>
                <td>{{ box.温控范围 }}</td>
                <td>{{ box.出库日期 || '—' }}</td>
                <td>{{ box.箱体状态 }}</td>
              </tr>
            </tbody>
          </table>
        </article>
        <p v-if="!stationGroups.length" class="empty-state">暂无站点盘点数据</p>
      </div>
    </template>

    <template v-else>
      <p class="page-desc">出库单按箱体类型拆分，明细挂在箱体编号下。</p>
      <table class="data-table">
        <thead>
          <tr>
            <th>出库单号</th>
            <th>出库日期</th>
            <th>箱体类型</th>
            <th>温控范围</th>
            <th>数量</th>
            <th>箱体明细（编号 → 归属站点）</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="record in checkoutRecordList" :key="record.出库单号">
            <td>{{ record.出库单号 }}</td>
            <td>{{ record.出库日期 }}</td>
            <td>{{ record.箱体类型 }}</td>
            <td>{{ record.温控范围 }}</td>
            <td>{{ record.数量 }}</td>
            <td>{{ record.明细.map((d: Record<string, string>) => `${d.箱体编号} → ${d.归属站点}`).join('、') }}</td>
          </tr>
          <tr v-if="!checkoutRecordList.length">
            <td colspan="6" class="empty-state">暂无出库记录</td>
          </tr>
        </tbody>
      </table>
    </template>

    <footer class="page-foot">
      <span>共 {{ total }} 条温控箱体记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="checkoutOpen" class="modal-mask">
      <div class="modal-panel">
        <header class="modal-head">
          <h3>批量出库</h3>
          <button class="link" type="button" @click="closeCheckout">关闭</button>
        </header>
        <div class="modal-body">
          <label class="filter-item">
            <span>出库日期（整组统一）</span>
            <input v-model="checkoutDate" type="date" />
          </label>
          <table v-if="checkoutItems.length" class="data-table">
            <thead>
              <tr>
                <th>箱体编号</th>
                <th>箱体类型</th>
                <th>温控范围</th>
                <th>归属站点（逐条填写）</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in checkoutItems" :key="item.entry_id">
                <td>{{ item.箱体编号 }}</td>
                <td>{{ item.箱体类型 }}</td>
                <td>{{ item.温控范围 }}</td>
                <td><input v-model="item.归属站点" placeholder="填写归属站点" /></td>
              </tr>
            </tbody>
          </table>
          <p v-else class="result-message">本次勾选的箱体已全部出库。</p>
          <p v-if="checkoutMessage" class="result-message">{{ checkoutMessage }}</p>
          <div v-if="checkoutFailed.length" class="result-block">
            <h4>未出库 {{ checkoutFailed.length }} 台，修正后可仅重试失败项（已出库的不会重复提交）</h4>
            <ul class="result-list">
              <li v-for="fail in checkoutFailed" :key="fail.entry_id">
                <strong>{{ fail.箱体编号 }}</strong>：{{ fail.message }}
              </li>
            </ul>
          </div>
          <div v-if="checkoutRecords.length" class="result-block">
            <h4>已生成出库单</h4>
            <ul class="result-list">
              <li v-for="record in checkoutRecords" :key="record.出库单号">
                {{ record.出库单号 }}（{{ record.箱体类型 }} × {{ record.数量 }}，温控范围 {{ record.温控范围 }}）
              </li>
            </ul>
          </div>
        </div>
        <footer class="modal-foot">
          <button
            class="btn primary"
            type="button"
            :disabled="submitting || !checkoutItems.length"
            @click="submitCheckout"
          >
            {{ checkoutFailed.length ? `仅重试失败项（${checkoutFailed.length}）` : '整组提交出库' }}
          </button>
          <button class="btn" type="button" @click="closeCheckout">关闭</button>
        </footer>
      </div>
    </div>

    <div v-if="recycleResult" class="modal-mask">
      <div class="modal-panel">
        <header class="modal-head">
          <h3>批量回收结果</h3>
          <button class="link" type="button" @click="recycleResult = null">关闭</button>
        </header>
        <div class="modal-body">
          <p class="result-message">{{ recycleResult.message }}</p>
          <div v-if="recycleResult.succeeded.length" class="result-block">
            <h4>已回收 {{ recycleResult.succeeded.length }} 台</h4>
            <ul class="result-list">
              <li v-for="item in recycleResult.succeeded" :key="item.entry_id">
                <strong>{{ item.箱体编号 }}</strong>：{{ item.message }}
              </li>
            </ul>
          </div>
          <div v-if="recycleResult.failed.length" class="result-block">
            <h4>需单独处理 {{ recycleResult.failed.length }} 台（未回收）</h4>
            <ul class="result-list">
              <li v-for="item in recycleResult.failed" :key="item.entry_id">
                <strong>{{ item.箱体编号 }}</strong>：{{ item.message }}
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>

    <div v-if="boxRecordsDetail" class="modal-mask">
      <div class="modal-panel">
        <header class="modal-head">
          <h3>{{ boxRecordsDetail.code }} 的出库记录</h3>
          <button class="link" type="button" @click="boxRecordsDetail = null">关闭</button>
        </header>
        <div class="modal-body">
          <table v-if="boxRecordsDetail.list.length" class="data-table">
            <thead>
              <tr>
                <th>出库单号</th>
                <th>出库日期</th>
                <th>归属站点</th>
                <th>温控范围</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="record in boxRecordsDetail.list" :key="record.出库单号">
                <td>{{ record.出库单号 }}</td>
                <td>{{ record.出库日期 }}</td>
                <td>{{ record.归属站点 }}</td>
                <td>{{ record.温控范围 }}</td>
              </tr>
            </tbody>
          </table>
          <p v-else class="empty-state">该箱体暂无出库记录</p>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, any>

const ENDPOINT = '/api/box'
const columns = ["箱体编号", "箱体类型", "内部容积", "保温材料", "保温材料状态", "温控范围", "出库日期", "归属站点", "箱体状态"]
const actions = ["调度出库", "清洗消毒", "申请报废"]
const statuses = ["可用", "使用中", "清洗中", "报废"]
const tabs = [
  { key: 'ledger', label: '箱体台账' },
  { key: 'station', label: '站点盘点' },
  { key: 'records', label: '出库记录' },
]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')
const stats = ref([{ label: '可用箱体', value: 0 }, { label: '使用中箱体', value: 0 }, { label: '清洗中箱体', value: 0 }])

const activeTab = ref('ledger')
const selectedIds = ref<number[]>([])

const checkoutOpen = ref(false)
const checkoutDate = ref(new Date().toISOString().slice(0, 10))
const checkoutItems = ref<Array<Record<string, any>>>([])
const checkoutFailed = ref<Array<Record<string, any>>>([])
const checkoutRecords = ref<Array<Record<string, any>>>([])
const checkoutMessage = ref('')
const submitting = ref(false)

const recycleResult = ref<Record<string, any> | null>(null)
const boxRecordsDetail = ref<{ code: string; list: Array<Record<string, any>> } | null>(null)
const stationGroups = ref<Array<Record<string, any>>>([])
const checkoutRecordList = ref<Array<Record<string, any>>>([])

const allVisibleSelected = computed(
  () => rows.value.length > 0 && rows.value.every((row) => selectedIds.value.includes(Number(row.id))),
)

function toggleSelect(id: number) {
  selectedIds.value = selectedIds.value.includes(id)
    ? selectedIds.value.filter((item) => item !== id)
    : [...selectedIds.value, id]
}

function toggleSelectAll() {
  if (allVisibleSelected.value) {
    const visible = new Set(rows.value.map((row) => Number(row.id)))
    selectedIds.value = selectedIds.value.filter((id) => !visible.has(id))
  } else {
    const merged = new Set([...selectedIds.value, ...rows.value.map((row) => Number(row.id))])
    selectedIds.value = [...merged]
  }
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '温控箱体登记入口尚未接入审批流'
}

function switchTab(tab: string) {
  activeTab.value = tab
  if (tab === 'station') {
    void loadStationInventory()
  } else if (tab === 'records') {
    void loadCheckoutRecords()
  }
}

function openCheckout() {
  checkoutItems.value = rows.value
    .filter((row) => selectedIds.value.includes(Number(row.id)))
    .map((row) => ({
      entry_id: Number(row.id),
      箱体编号: row.箱体编号,
      箱体类型: row.箱体类型,
      温控范围: row.温控范围,
      归属站点: '',
    }))
  checkoutFailed.value = []
  checkoutRecords.value = []
  checkoutMessage.value = ''
  checkoutOpen.value = true
}

function closeCheckout() {
  checkoutOpen.value = false
  selectedIds.value = []
  void reload()
  void loadStats()
}

async function submitCheckout() {
  submitting.value = true
  checkoutMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/batch-checkout`, {
      method: 'POST',
      body: JSON.stringify({
        出库日期: checkoutDate.value,
        items: checkoutItems.value.map((item) => ({ entry_id: item.entry_id, 归属站点: item.归属站点 })),
      }),
    })
    if (!response.ok) {
      throw new Error(`批量出库接口返回 ${response.status}`)
    }
    const result = await response.json()
    checkoutMessage.value = result.message ?? ''
    checkoutFailed.value = result.failed ?? []
    checkoutRecords.value = [...checkoutRecords.value, ...(result.records ?? [])]
    // 成功的直接移出待提交列表，只留失败项供修正后重试，已出库的不会被回滚或重复提交
    const failedIds = new Set(checkoutFailed.value.map((item) => item.entry_id))
    checkoutItems.value = checkoutItems.value.filter((item) => failedIds.has(item.entry_id))
    await reload()
    await loadStats()
  } catch (error) {
    checkoutMessage.value = error instanceof Error ? error.message : '批量出库失败'
  } finally {
    submitting.value = false
  }
}

async function runBatchRecycle() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/batch-recycle`, {
      method: 'POST',
      body: JSON.stringify({ entry_ids: selectedIds.value }),
    })
    if (!response.ok) {
      throw new Error(`批量回收接口返回 ${response.status}`)
    }
    recycleResult.value = await response.json()
    selectedIds.value = []
    await reload()
    await loadStats()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '批量回收失败'
  }
}

async function viewBoxRecords(row: Row) {
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error(`箱体明细接口返回 ${response.status}`)
    }
    const payload = await response.json()
    boxRecordsDetail.value = { code: String(row.箱体编号), list: payload.出库记录 ?? [] }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '出库记录读取失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('温控箱体动作未生效，请稍后重试')
    }
    await reload()
    await loadStats()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '温控箱体操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value) query.set('keyword', keyword.value)
  if (statusFilter.value) query.set('status', statusFilter.value)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('温控箱体列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '温控箱体列表读取失败'
  }
}

async function loadStats() {
  try {
    const response = await request(`${ENDPOINT}?size=200`)
    if (!response.ok) return
    const payload = await response.json()
    const items: Row[] = payload.items ?? []
    stats.value = [
      { label: '可用箱体', value: items.filter((item) => item.status === '可用').length },
      { label: '使用中箱体', value: items.filter((item) => item.status === '使用中').length },
      { label: '清洗中箱体', value: items.filter((item) => item.status === '清洗中').length },
    ]
  } catch {
    // 统计卡片失败不阻断页面
  }
}

async function loadStationInventory() {
  try {
    const response = await request(`${ENDPOINT}/station-inventory`)
    if (!response.ok) {
      throw new Error(`站点盘点接口返回 ${response.status}`)
    }
    const payload = await response.json()
    stationGroups.value = payload.items ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '站点盘点读取失败'
  }
}

async function loadCheckoutRecords() {
  try {
    const response = await request(`${ENDPOINT}/checkout-records`)
    if (!response.ok) {
      throw new Error(`出库记录接口返回 ${response.status}`)
    }
    const payload = await response.json()
    checkoutRecordList.value = payload.items ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '出库记录读取失败'
  }
}

onMounted(() => {
  void reload()
  void loadStats()
})
</script>
