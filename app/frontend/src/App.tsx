import { useState } from "react";
import { useAuth } from "./auth/AuthContext";
import { AppShell } from "./components/layout/AppShell";
import { AdminPage } from "./pages/AdminPage";
import { ApprovePage } from "./pages/ApprovePage";
import { AuthPage } from "./pages/AuthPage";
import { DashboardPage } from "./pages/DashboardPage";
import { NewsletterPage } from "./pages/NewsletterPage";
import { PurchasesPage } from "./pages/PurchasesPage";

// Ссылка из письма администратору: /approve/{guid} (бэк отдаёт на неё index.html)
function readApproveGuid(): string | null {
  const match = window.location.pathname.match(/^\/approve\/([^/]+)\/?$/);
  return match ? decodeURIComponent(match[1]) : null;
}

function App() {
  const { token } = useAuth();
  const [activePage, setActivePage] = useState("dashboard");
  const [approveGuid, setApproveGuid] = useState(readApproveGuid);

  // Путь /approve/... сохраняется, пока админ входит, — после входа сразу откроется подтверждение
  if (!token) return <AuthPage />;

  if (approveGuid) {
    return (
      <ApprovePage
        guid={approveGuid}
        onExit={() => {
          window.history.replaceState(null, "", "/");
          setApproveGuid(null);
        }}
      />
    );
  }

  return (
    <AppShell activePage={activePage} onChangePage={setActivePage}>
      {activePage === "dashboard" && <DashboardPage />}
      {activePage === "purchases" && <PurchasesPage />}
      {activePage === "newsletter" && <NewsletterPage />}
      {activePage === "admin" && <AdminPage />}
    </AppShell>
  );
}

export default App;
