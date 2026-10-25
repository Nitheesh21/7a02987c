import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { useCutoff } from "./useCutoff";
import Accuracy from "./pages/Accuracy";
import Decision from "./pages/Decision";
import Method from "./pages/Method";

export default function App() {
  const { cutoff, setCutoff, meta } = useCutoff();
  const { search } = useLocation();
  return (
    <>
      <header className="top">
        <div className="wrap top-inner">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true" />
            Wind forecast desk
          </div>
          <nav aria-label="Main">
            <NavLink to={{ pathname: "/", search }} end>Tomorrow's wind</NavLink>
            <NavLink to={{ pathname: "/accuracy", search }}>How accurate</NavLink>
            <NavLink to={{ pathname: "/method", search }}>Method</NavLink>
          </nav>
          <label className="cutoff">
            <span>Cutoff on the day before (UK time)</span>
            <input
              type="time"
              value={cutoff}
              onChange={(e) => setCutoff(e.target.value)}
              disabled={!meta.data}
              aria-label="Day-ahead cutoff time, UK local"
            />
          </label>
        </div>
      </header>
      <main className="wrap">
        {meta.isError && <p className="error" role="alert">Cannot reach the data service. {String(meta.error)}</p>}
        <Routes>
          <Route path="/" element={<Decision />} />
          <Route path="/accuracy" element={<Accuracy />} />
          <Route path="/method" element={<Method />} />
          <Route path="*" element={<p>Page not found.</p>} />
        </Routes>
      </main>
      <footer className="wrap foot">
        Data: Elexon BMRS (FUELHH actuals, WINDFOR forecasts), Great Britain national level. Pilot window{" "}
        {meta.data ? `${meta.data.delivery_start} to ${meta.data.delivery_end}` : ""}.
      </footer>
    </>
  );
}
