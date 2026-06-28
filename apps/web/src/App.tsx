import { Route, Routes } from "react-router-dom";
import Login from "./routes/Login";
import Dashboard from "./routes/Dashboard";
import CountriesList from "./routes/CountriesList";
import CountryProfile from "./routes/CountryProfile";
import CountryComparison from "./routes/CountryComparison";
import ScenarioEngine from "./routes/ScenarioEngine";
import ScenarioView from "./routes/ScenarioView";
import AdminSynopses from "./routes/AdminSynopses";
import NewsIntelligence from "./routes/NewsIntelligence";
import ReportsList from "./routes/ReportsList";
import ReportGenerator from "./routes/ReportGenerator";
import RequireAuth from "./routes/RequireAuth";
import { AppToaster } from "./components/Toast";

export default function App() {
  return (
    <>
      <AppToaster />
      <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<RequireAuth><Dashboard /></RequireAuth>} />
      <Route path="/countries" element={<RequireAuth><CountriesList /></RequireAuth>} />
      <Route path="/countries/compare" element={<RequireAuth><CountryComparison /></RequireAuth>} />
      <Route path="/countries/:iso3" element={<RequireAuth><CountryProfile /></RequireAuth>} />
      <Route path="/scenarios/new" element={<RequireAuth><ScenarioEngine /></RequireAuth>} />
      <Route path="/scenarios/:id" element={<RequireAuth><ScenarioView /></RequireAuth>} />
      <Route path="/news" element={<RequireAuth><NewsIntelligence /></RequireAuth>} />
      <Route path="/admin/synopses" element={<RequireAuth><AdminSynopses /></RequireAuth>} />
      <Route path="/reports" element={<RequireAuth><ReportsList /></RequireAuth>} />
      <Route path="/reports/new" element={<RequireAuth><ReportGenerator /></RequireAuth>} />
    </Routes>
    </>
  );
}
