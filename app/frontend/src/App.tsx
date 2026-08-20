import { useState } from "react";
import { AppShell } from "./components/layout/AppShell";
import { AdminPage } from "./pages/AdminPage";
import { DashboardPage } from "./pages/DashboardPage";
import { NewsletterPage } from "./pages/NewsletterPage";
import { PurchasesPage } from "./pages/PurchasesPage";

function App() {
  const [activePage, setActivePage] = useState("dashboard");

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