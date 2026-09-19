import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { ProtectedRoute } from './components/ProtectedRoute'
import { CardEntryPage } from './pages/CardEntryPage'
import { HomePage } from './pages/HomePage'
import { LoginPage } from './pages/LoginPage'
import { NewReadingPage } from './pages/NewReadingPage'
import { ReadingHistoryPage } from './pages/ReadingHistoryPage'
import { ReadingResultPage } from './pages/ReadingResultPage'
import { RegisterPage } from './pages/RegisterPage'
import { SpreadReviewPage } from './pages/SpreadReviewPage'

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/readings" element={<ReadingHistoryPage />} />
          <Route path="/readings/new" element={<NewReadingPage />} />
          <Route path="/readings/:readingId/draw" element={<CardEntryPage />} />
          <Route path="/readings/:readingId/result" element={<ReadingResultPage />} />
          <Route path="/readings/:readingId" element={<SpreadReviewPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

export default App
