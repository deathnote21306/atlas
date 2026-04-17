import { Route, Routes } from "react-router-dom";
import Login from "./routes/Login";
import Home from "./routes/Home";
import CountriesList from "./routes/CountriesList";
import CountryProfile from "./routes/CountryProfile";
import RequireAuth from "./routes/RequireAuth";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<RequireAuth><Home /></RequireAuth>} />
      <Route path="/countries" element={<RequireAuth><CountriesList /></RequireAuth>} />
      <Route path="/countries/:iso3" element={<RequireAuth><CountryProfile /></RequireAuth>} />
    </Routes>
  );
}
