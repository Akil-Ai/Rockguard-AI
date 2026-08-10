import React from 'react'
import ReactDOM from 'react-dom/client'
import { createHashRouter, RouterProvider } from 'react-router-dom'

import 'leaflet/dist/leaflet.css'
import './index.css'

import Layout from './components/Layout'
import { AppProvider } from './store/AppContext'
import Alerts from './pages/Alerts'
import Dashboard from './pages/Dashboard'
import HistoryPage from './pages/History'
import MineMap from './pages/MineMap'
import RiskPrediction from './pages/RiskPrediction'
import RockAnalysis from './pages/RockAnalysis'
import SensorMonitoring from './pages/SensorMonitoring'

// Hash routing: the console is a static bundle, so this works when it is opened
// from a file path or served without a history-API fallback rule.
const router = createHashRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'map', element: <MineMap /> },
      { path: 'rock-analysis', element: <RockAnalysis /> },
      { path: 'sensors', element: <SensorMonitoring /> },
      { path: 'prediction', element: <RiskPrediction /> },
      { path: 'alerts', element: <Alerts /> },
      { path: 'history', element: <HistoryPage /> },
    ],
  },
])

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AppProvider>
      <RouterProvider router={router} />
    </AppProvider>
  </React.StrictMode>,
)
