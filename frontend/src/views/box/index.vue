<template>
  <section class="page" data-module="box">
    <header class="page-head">
      <div>
        <h2>温控箱体管理</h2>
        <p class="page-desc">围绕箱体编号、箱体类型、保温材料、温控范围做登记与出入库流转，支持勾选多个箱体批量出库与批量回收。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="openRecords()">出入库记录</button>
        <button class="btn" type="button" @click="exportRows">导出温控箱体清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload()">
      <label class="filter-item">
        <span>箱体编号 / 归属站点</span>
        <input v-model="filters.keyword" placeholder="按箱体编号或站点检索" />
      </label>
      <label class="filter-item">
        <span>箱体状态</span>
        <select v-model="filters.status">
          <option value="">全部</option>
          <option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <div class="batch-bar">
      <label><input type="checkbox" :checked="allChecked" :indeterminate.prop="indeterminate" @change="toggleAll" /> 全选本页</label>
      <span>已勾选 <strong>{{ selectedIds.length }}</strong> 个箱体</span>
      <span class="spacer"></span>
      <button class="btn primary" type="button" :disabled="!selectedIds.length" @click="openOutbound">批量出库</button>
      <button class="btn" type="button" :disabled="!selectedIds.length" @click="openReturn">批量回收</button>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th style="width: 40px">选择</th>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th style="width: 230px">可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td><input type="checkbox" :checked="isSelected(row.id as number)" @change="toggleOne(row.id as number)" /></td>
          <td>{{ row['箱体编号'] ?? '—' }}</td>
          <td>{{ row['箱体类型'] ?? '—' }}</td>
          <td>{{ row['内部容积'] ?? '—' }}</td>
          <td>
            {{ row['保温材料'] ?? '—' }}
            <span v-if="row['保温材料状态'] === '受损'" class="tag damage">材料受损</span>
          </td>
          <td>{{ row['温控范围'] ?? '—' }}</td>
          <td>{{ row['出库日期'] || '—' }}</td>
          <td>{{ row['归属站点'] || '在库' }}</td>
          <td><span :class="['tag', statusClass(row.status as string)]">{{ row['箱体状态'] ?? '—' }}</span></td>
          <td class="row-actions">
            <button class="link" type="button" @click="openRecords(row)">记录</button>
            <button v-if="row.status === '可用'" class="link" type="button" @click="openSingleOutbound(row)">调度出库</button>
            <button v-if="row.status !== '报废' && row['保温材料状态'] !== '受损'" class="link" type="button" @click="runSimpleAction('标记保温材料受损', row)">标记受损</button>
            <button v-if="row['保温材料状态'] === '受损'" class="link" type="button" @click="runSimpleAction('保温材料修复', row)">材料修复</button>
            <button v-if="row.status !== '报废' && row.status !== '清洗中'" class="link" type="button" @click="runSimpleAction('清洗消毒', row)">清洗消毒</button>
            <button v-if="row.status !== '报废'" class="link" type="button" @click="runSimpleAction('申请报废', row)">申请报废</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 2" class="empty-state">暂无温控箱体数据</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条温控箱体记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 批量出库 -->
    <div v-if="outbound.open" class="modal-mask" @click.self="closeOutbound">
      <div class="modal wide">
        <div class="modal-head">
          <h3>批量出库（{{ outbound.rows.length }} 个箱体，按箱体类型自动拆分出库记录）</h3>
          <button class="modal-close" type="button" @click="closeOutbound">×</button>
        </div>
        <div class="modal-body">
          <template v-if="!outbound.done">
            <p class="modal-tip">出库日期整组统一填写；归属站点请逐条填写。只有「可用且保温材料正常」的箱体允许出库，受损或已报废的会被逐条拦下。</p>
            <div class="form-line">
              <label>
                <span>统一出库日期</span>
                <input v-model="outbound.date" type="date" />
              </label>
            </div>
            <table class="data-table">
              <thead>
                <tr><th>箱体编号</th><th>箱体类型</th><th>温控范围</th><th>当前状态</th><th>归属站点（逐条填写）</th></tr>
              </thead>
              <tbody>
                <tr v-for="item in outbound.rows" :key="item.id">
                  <td>{{ item['箱体编号'] }}</td>
                  <td>{{ item['箱体类型'] }}</td>
                  <td>{{ item['温控范围'] }}</td>
                  <td>
                    <span :class="['tag', statusClass(item.status)]">{{ item.status }}</span>
                    <span v-if="item['保温材料状态'] === '受损'" class="tag damage">材料受损</span>
                  </td>
                  <td><input v-model="item.station" type="text" placeholder="填写归属站点" style="width: 200px" /></td>
                </tr>
              </tbody>
            </table>
          </template>
          <template v-else>
            <div :class="['result-banner', bannerClass(outbound.result)]">{{ outbound.result?.message }}</div>
            <div v-if="outbound.result?.records?.length" class="result-box">
              <div class="result-title ok-text">已生成出库记录（{{ outbound.result.records.length }} 条，同类型一条）</div>
              <ul>
                <li v-for="rec in outbound.result.records" :key="rec['记录编号']">
                  <span class="code">{{ rec['记录编号'] }}</span>
                  <span>{{ rec['箱体类型'] }} · {{ rec['温控范围'] }} · {{ rec['数量'] }} 个：{{ rec['箱体编号'].join('、') }} → {{ rec['归属站点'] }}</span>
                </li>
              </ul>
            </div>
            <div v-if="succeededItems.length" class="result-box">
              <div class="result-title ok-text">出库成功（{{ succeededItems.length }} 个，已切换为「使用中」，不会回滚）</div>
              <ul>
                <li v-for="it in succeededItems" :key="String(it.id)"><span class="code">{{ it['箱体编号'] }}</span><span>→ {{ it['归属站点'] }}</span></li>
              </ul>
            </div>
            <div v-if="failedItems.length" class="result-box">
              <div class="result-title error-text">被卡住（{{ failedItems.length }} 个，修好后可只重试失败项）</div>
              <ul>
                <li v-for="it in failedItems" :key="String(it.id)">
                  <span class="code">{{ it['箱体编号'] }}</span>
                  <span class="error-text">{{ it.reason }}</span>
                </li>
              </ul>
            </div>
          </template>
        </div>
        <div class="modal-foot">
          <template v-if="!outbound.done">
            <button class="btn ghost" type="button" @click="closeOutbound">取消</button>
            <button class="btn primary" type="button" :disabled="outbound.submitting" @click="submitOutbound">整组提交出库</button>
          </template>
          <template v-else>
            <button class="btn" type="button" @click="closeOutbound">关闭</button>
            <button v-if="failedItems.length" class="btn primary" type="button" :disabled="outbound.submitting" @click="retryFailedOutbound">
              仅重试失败的 {{ failedItems.length }} 个
            </button>
          </template>
        </div>
      </div>
    </div>

    <!-- 批量回收 -->
    <div v-if="ret.open" class="modal-mask" @click.self="closeReturn">
      <div class="modal wide">
        <div class="modal-head">
          <h3>批量回收</h3>
          <button class="modal-close" type="button" @click="closeReturn">×</button>
        </div>
        <div class="modal-body">
          <template v-if="!ret.done">
            <p v-if="ret.loading" class="modal-tip">正在核对箱体状况…</p>
            <template v-else>
              <div class="result-banner good" v-if="ret.reusable.length">本次将回收以下 {{ ret.reusable.length }} 个还能使用的箱体（回收后状态变为「可用」，清空归属站点与出库日期）。</div>
              <div class="result-banner bad" v-if="ret.excluded.length">以下 {{ ret.excluded.length }} 个箱体已被单独挑出，不参与本次回收。</div>
              <div v-if="ret.reusable.length" class="result-box">
                <div class="result-title ok-text">可回收（{{ ret.reusable.length }}）</div>
                <ul>
                  <li v-for="b in ret.reusable" :key="String(b.id)">
                    <span class="code">{{ b['箱体编号'] }}</span>
                    <span>{{ b['箱体类型'] }} · {{ b['温控范围'] }} · 来自 {{ b['归属站点'] || '在库' }}</span>
                  </li>
                </ul>
              </div>
              <div v-if="ret.excluded.length" class="result-box">
                <div class="result-title error-text">已剔除（{{ ret.excluded.length }}）</div>
                <ul>
                  <li v-for="b in ret.excluded" :key="String(b.id)">
                    <span class="code">{{ b['箱体编号'] }}</span>
                    <span class="muted-text">{{ b['箱体类型'] }} · 当前「{{ b['箱体状态'] }}」</span>
                    <span class="error-text">原因：{{ b.reason }}</span>
                  </li>
                </ul>
              </div>
            </template>
          </template>
          <template v-else>
            <div :class="['result-banner', bannerClass(ret.result)]">{{ ret.result?.message }}</div>
            <div v-if="ret.result?.records?.length" class="result-box">
              <div class="result-title ok-text">已生成回收记录（{{ ret.result.records.length }} 条）</div>
              <ul>
                <li v-for="rec in ret.result.records" :key="rec['记录编号']">
                  <span class="code">{{ rec['记录编号'] }}</span>
                  <span>{{ rec['箱体类型'] }} · {{ rec['数量'] }} 个：{{ rec['箱体编号'].join('、') }}</span>
                </li>
              </ul>
            </div>
            <div v-if="ret.result && retOkItems.length" class="result-box">
              <div class="result-title ok-text">回收成功（{{ retOkItems.length }}）</div>
              <ul>
                <li v-for="it in retOkItems" :key="String(it.id)"><span class="code">{{ it['箱体编号'] }}</span><span>已回库为「可用」</span></li>
              </ul>
            </div>
            <div v-if="ret.result && retFailItems.length" class="result-box">
              <div class="result-title error-text">被卡住（{{ retFailItems.length }}）</div>
              <ul>
                <li v-for="it in retFailItems" :key="String(it.id)"><span class="code">{{ it['箱体编号'] }}</span><span class="error-text">{{ it.reason }}</span></li>
              </ul>
            </div>
          </template>
        </div>
        <div class="modal-foot">
          <template v-if="!ret.done">
            <button class="btn ghost" type="button" @click="closeReturn">取消</button>
            <button class="btn primary" type="button" :disabled="ret.loading || !ret.reusable.length || ret.submitting" @click="submitReturn">
              回收选中的 {{ ret.reusable.length }} 个
            </button>
          </template>
          <template v-else>
            <button class="btn" type="button" @click="closeReturn">关闭</button>
            <button v-if="retFailItems.length" class="btn primary" type="button" :disabled="ret.submitting" @click="retryFailedReturn">
              仅重试失败的 {{ retFailItems.length }} 个
            </button>
          </template>
        </div>
      </div>
    </div>

    <!-- 出入库记录 -->
    <div v-if="recordsModal.open" class="modal-mask" @click.self="recordsModal.open = false">
      <div class="modal wide">
        <div class="modal-head">
          <h3>出入库记录<template v-if="recordsModal.boxCode"> · 箱体 {{ recordsModal.boxCode }}</template></h3>
          <button class="modal-close" type="button" @click="recordsModal.open = false">×</button>
        </div>
        <div class="modal-body">
          <form class="filter-bar" @submit.prevent="loadRecords">
            <label class="filter-item">
              <span>记录编号 / 箱体编号</span>
              <input v-model="recordsModal.keyword" placeholder="按编号检索" />
            </label>
            <button class="btn" type="submit">查询</button>
          </form>
          <table class="data-table">
            <thead>
              <tr><th>记录编号</th><th>类型</th><th>箱体类型</th><th>温控范围</th><th>数量</th><th>箱体编号</th><th>归属站点</th><th>出库日期</th><th>回收日期</th></tr>
            </thead>
            <tbody>
              <tr v-for="rec in recordsModal.items" :key="rec['记录编号']">
                <td>{{ rec['记录编号'] }}</td>
                <td><span :class="['tag', rec['记录类型'] === '出库' ? 'using' : 'avail']">{{ rec['记录类型'] }}</span></td>
                <td>{{ rec['箱体类型'] }}</td>
                <td>{{ rec['温控范围'] }}</td>
                <td>{{ rec['数量'] }}</td>
                <td>{{ rec['箱体编号'].join('、') }}</td>
                <td>{{ rec['归属站点'] || '—' }}</td>
                <td>{{ rec['出库日期'] || '—' }}</td>
                <td>{{ rec['回收日期'] || '—' }}</td>
              </tr>
              <tr v-if="!recordsModal.items.length">
                <td colspan="9" class="empty-state">暂无出入库记录</td>
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

type Row = Record<string, string | number | boolean | string[] | null>
type ResultItem = { id: number; 箱体编号: string; 归属站点?: string; ok: boolean; reason: string }
type BoxRecord = Record<string, string | number | boolean | string[] | null> & {
  记录编号: string
  记录类型: string
  箱体类型: string
  温控范围: string
  数量: number
  箱体编号: string[]
  归属站点: string
  出库日期: string
  回收日期: string
}
type BatchResult = { ok: boolean; message: string; items: ResultItem[]; records: BoxRecord[] }
type PreviewBox = Row & { reason?: string }

const ENDPOINT = '/api/box'
const columns = ['箱体编号', '箱体类型', '内部容积', '保温材料', '温控范围', '出库日期', '归属站点', '箱体状态']
const statuses = ['可用', '使用中', '清洗中', '报废']

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({ keyword: '', status: '' })
const selectedIds = ref<number[]>([])

const stats = computed(() => [
  { label: '可用箱体', value: rows.value.filter((r) => r.status === '可用').length },
  { label: '使用中箱体', value: rows.value.filter((r) => r.status === '使用中').length },
  { label: '清洗中箱体', value: rows.value.filter((r) => r.status === '清洗中').length },
  { label: '保温材料受损', value: rows.value.filter((r) => r['保温材料状态'] === '受损').length },
])

function statusClass(status: string): string {
  return { 可用: 'avail', 使用中: 'using', 清洗中: 'wash', 报废: 'scrap' }[status] ?? ''
}

function isSelected(id: number): boolean {
  return selectedIds.value.includes(id)
}

const allChecked = computed(() => rows.value.length > 0 && rows.value.every((r) => isSelected(r.id as number)))
const indeterminate = computed(() => selectedIds.value.length > 0 && !allChecked.value)

function toggleOne(id: number) {
  if (isSelected(id)) {
    selectedIds.value = selectedIds.value.filter((v) => v !== id)
  } else {
    selectedIds.value = [...selectedIds.value, id]
  }
}

function toggleAll() {
  if (allChecked.value) {
    const pageIds = rows.value.map((r) => r.id as number)
    selectedIds.value = selectedIds.value.filter((id) => !pageIds.includes(id))
  } else {
    selectedIds.value = [...new Set([...selectedIds.value, ...rows.value.map((r) => r.id as number)])]
  }
}

function resetFilters() {
  filters.value = { keyword: '', status: '' }
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function reload(keepSelection = true) {
  errorMessage.value = ''
  const query = new URLSearchParams(
    Object.entries(filters.value).filter(([, v]) => v) as [string, string][],
  ).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}&size=200`)
    if (!response.ok) {
      throw new Error('温控箱体列表读取失败')
    }
    const payload = await response.json()
    rows.value = (payload.items ?? []) as Row[]
    total.value = payload.total ?? rows.value.length
    if (!keepSelection) {
      selectedIds.value = []
    } else {
      // 过滤/翻页后剔除已不存在的勾选项
      const ids = new Set(rows.value.map((r) => r.id as number))
      selectedIds.value = selectedIds.value.filter((id) => ids.has(id))
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '温控箱体列表读取失败'
  }
}

// ------------------------------------------------------------- 单条动作
async function runSimpleAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload?.message || '温控箱体动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '温控箱体操作失败'
  }
}

function openSingleOutbound(row: Row) {
  // 单条出库复用批量弹窗：预置一行，归属站点留空待填。
  outbound.rows = [{ id: row.id as number, '箱体编号': row['箱体编号'] as string, '箱体类型': row['箱体类型'] as string, '温控范围': row['温控范围'] as string, status: row.status as string, '保温材料状态': row['保温材料状态'] as string, station: '' }]
  outbound.open = true
  outbound.done = false
  outbound.result = null
  outbound.date = today()
}

// ------------------------------------------------------------- 批量出库
type OutboundRow = { id: number; '箱体编号': string; '箱体类型': string; '温控范围': string; status: string; '保温材料状态': string; station: string }

const outbound = reactive({
  open: false,
  submitting: false,
  date: '',
  rows: [] as OutboundRow[],
  done: false,
  result: null as BatchResult | null,
})

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

const failedItems = computed(() => (outbound.result?.items ?? []).filter((it) => !it.ok))
const succeededItems = computed(() => (outbound.result?.items ?? []).filter((it) => it.ok))

function openOutbound() {
  const selected = rows.value.filter((r) => isSelected(r.id as number))
  outbound.rows = selected.map((r) => ({
    id: r.id as number,
    '箱体编号': r['箱体编号'] as string,
    '箱体类型': r['箱体类型'] as string,
    '温控范围': r['温控范围'] as string,
    status: r.status as string,
    '保温材料状态': r['保温材料状态'] as string,
    station: (r['归属站点'] as string) ?? '',
  }))
  outbound.date = today()
  outbound.done = false
  outbound.result = null
  outbound.open = true
}

function closeOutbound() {
  outbound.open = false
  void reload()
}

async function submitOutbound() {
  outbound.submitting = true
  errorMessage.value = ''
  try {
    const items = outbound.rows.map((r) => ({ id: r.id, 箱体编号: r['箱体编号'], 归属站点: r.station.trim() }))
    const data = await postBatch<BatchResult>(`${ENDPOINT}/batch-outbound`, { items, 出库日期: outbound.date })
    outbound.result = data
    outbound.done = true
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '批量出库失败'
  } finally {
    outbound.submitting = false
  }
}

async function retryFailedOutbound() {
  // 只把失败项重新提交；保留用户在弹窗里为失败项填过的站点值。
  outbound.submitting = true
  errorMessage.value = ''
  try {
    const stationMap = new Map(outbound.rows.map((r) => [r.id, r.station]))
    const items = failedItems.value.map((it) => ({
      id: it.id,
      箱体编号: it.箱体编号,
      归属站点: stationMap.get(it.id) ?? it.归属站点 ?? '',
    }))
    const data = await postBatch<BatchResult>(`${ENDPOINT}/batch-outbound`, { items, 出库日期: outbound.date })
    // 合并本次结果：之前成功的保持成功，新结果覆盖同 id 项。
    const prevOk = succeededItems.value.filter((it) => !data.items.some((n) => n.id === it.id))
    outbound.result = { ...data, items: [...prevOk, ...data.items], message: data.message }
    outbound.done = true
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '重试失败'
  } finally {
    outbound.submitting = false
  }
}

// ------------------------------------------------------------- 批量回收
const ret = reactive({
  open: false,
  loading: false,
  submitting: false,
  reusable: [] as PreviewBox[],
  excluded: [] as PreviewBox[],
  done: false,
  result: null as BatchResult | null,
})

const retOkItems = computed(() => (ret.result?.items ?? []).filter((it) => it.ok))
const retFailItems = computed(() => (ret.result?.items ?? []).filter((it) => !it.ok))

async function openReturn() {
  ret.open = true
  ret.loading = true
  ret.done = false
  ret.result = null
  try {
    const ids = rows.value.filter((r) => isSelected(r.id as number)).map((r) => r.id)
    const response = await request(`${ENDPOINT}/batch-return/preview`, {
      method: 'POST',
      body: JSON.stringify({ items: ids.map((id) => ({ id })) }),
    })
    if (!response.ok) {
      throw new Error('回收预览失败，请稍后重试')
    }
    const data = await response.json()
    ret.reusable = (data.reusable ?? []) as PreviewBox[]
    ret.excluded = (data.excluded ?? []) as PreviewBox[]
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '回收预览失败'
    ret.open = false
  } finally {
    ret.loading = false
  }
}

function closeReturn() {
  ret.open = false
  void reload()
}

async function submitReturn() {
  ret.submitting = true
  errorMessage.value = ''
  try {
    const items = ret.reusable.map((b) => ({ id: b.id as number, 箱体编号: b['箱体编号'] as string }))
    const data = await postBatch<BatchResult>(`${ENDPOINT}/batch-return`, { items })
    ret.result = data
    ret.done = true
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '批量回收失败'
  } finally {
    ret.submitting = false
  }
}

async function retryFailedReturn() {
  ret.submitting = true
  errorMessage.value = ''
  try {
    const items = retFailItems.value.map((it) => ({ id: it.id, 箱体编号: it.箱体编号 }))
    const data = await postBatch<BatchResult>(`${ENDPOINT}/batch-return`, { items })
    const prevOk = retOkItems.value.filter((it) => !data.items.some((n) => n.id === it.id))
    ret.result = { ...data, items: [...prevOk, ...data.items], message: data.message }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '重试失败'
  } finally {
    ret.submitting = false
  }
}

// ------------------------------------------------------------- 出入库记录
const recordsModal = reactive({
  open: false,
  keyword: '',
  boxCode: '',
  items: [] as BoxRecord[],
})

async function openRecords(row?: Row) {
  recordsModal.open = true
  recordsModal.boxCode = row ? String(row['箱体编号'] ?? '') : ''
  recordsModal.keyword = recordsModal.boxCode
  await loadRecords()
}

async function loadRecords() {
  try {
    const query = new URLSearchParams({ keyword: recordsModal.keyword, size: '200' }).toString()
    const response = await request(`${ENDPOINT}/records?${query}`)
    if (!response.ok) {
      throw new Error('出入库记录读取失败')
    }
    const payload = await response.json()
    recordsModal.items = (payload.items ?? []) as BoxRecord[]
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '出入库记录读取失败'
  }
}

// ------------------------------------------------------------- 通用
async function postBatch<T>(url: string, body: unknown): Promise<T> {
  const response = await request(url, { method: 'POST', body: JSON.stringify(body) })
  const data = (await response.json()) as T
  if (!response.ok) {
    throw new Error((data as { message?: string }).message ?? '批量操作未生效，请稍后重试')
  }
  return data
}

function bannerClass(result: BatchResult | null): string {
  if (!result) return ''
  if (!result.items.length) return result.ok ? 'good' : 'bad'
  return result.ok ? 'good' : result.items.some((it) => it.ok) ? 'warn' : 'bad'
}

onMounted(() => {
  void reload(false)
})
</script>
