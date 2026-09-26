import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from '@/views/Dashboard.vue'
const Fleet = () => import('@/views/fleet/index.vue')
const Driver = () => import('@/views/driver/index.vue')
const Order = () => import('@/views/order/index.vue')
const Dispatch3 = () => import('@/views/dispatch3/index.vue')
const Temp = () => import('@/views/temp/index.vue')
const Door = () => import('@/views/door/index.vue')
const Returntrip = () => import('@/views/returntrip/index.vue')
const Abnormal2 = () => import('@/views/abnormal2/index.vue')
const Renew = () => import('@/views/renew/index.vue')
const Refriger = () => import('@/views/refriger/index.vue')
const Box = () => import('@/views/box/index.vue')
const Inventory = () => import('@/views/inventory/index.vue')
const Route = () => import('@/views/route/index.vue')
const Sensor = () => import('@/views/sensor/index.vue')
const Cost = () => import('@/views/cost/index.vue')
const Client2 = () => import('@/views/client2/index.vue')
const Checkin = () => import('@/views/checkin/index.vue')
const Accident = () => import('@/views/accident/index.vue')
const Roadcheck = () => import('@/views/roadcheck/index.vue')
const Clean2 = () => import('@/views/clean2/index.vue')
const Contract2 = () => import('@/views/contract2/index.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: Dashboard },
    { path: '/fleet', name: 'fleet', component: Fleet },
    { path: '/driver', name: 'driver', component: Driver },
    { path: '/order', name: 'order', component: Order },
    { path: '/dispatch3', name: 'dispatch3', component: Dispatch3 },
    { path: '/temp', name: 'temp', component: Temp },
    { path: '/door', name: 'door', component: Door },
    { path: '/returntrip', name: 'returntrip', component: Returntrip },
    { path: '/abnormal2', name: 'abnormal2', component: Abnormal2 },
    { path: '/renew', name: 'renew', component: Renew },
    { path: '/refriger', name: 'refriger', component: Refriger },
    { path: '/box', name: 'box', component: Box },
    { path: '/inventory', name: 'inventory', component: Inventory },
    { path: '/route', name: 'route', component: Route },
    { path: '/sensor', name: 'sensor', component: Sensor },
    { path: '/cost', name: 'cost', component: Cost },
    { path: '/client2', name: 'client2', component: Client2 },
    { path: '/checkin', name: 'checkin', component: Checkin },
    { path: '/accident', name: 'accident', component: Accident },
    { path: '/roadcheck', name: 'roadcheck', component: Roadcheck },
    { path: '/clean2', name: 'clean2', component: Clean2 },
    { path: '/contract2', name: 'contract2', component: Contract2 },
  ],
})

export default router
