import { Route, Routes, Navigate } from 'react-router-dom';
import { Shell } from '@/components/layout/Shell';
import Dashboard from '@/pages/Dashboard';
import Messages from '@/pages/Messages';
import Admin from '@/pages/Admin';
import AdminDocs from '@/pages/AdminDocs';
import AdminChangelog from '@/pages/AdminChangelog';
import AdminPermissions from '@/pages/AdminPermissions';
import Memory from '@/pages/Memory';
import NotFound from '@/pages/NotFound';

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/messages" element={<Messages />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="/admin/docs" element={<AdminDocs />} />
        <Route path="/admin/changelog" element={<AdminChangelog />} />
        <Route path="/admin/permissions" element={<AdminPermissions />} />
        <Route path="/memory" element={<Memory />} />
        <Route path="/memory/:agent" element={<Memory />} />
        <Route path="/index.html" element={<Navigate to="/" replace />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Shell>
  );
}
