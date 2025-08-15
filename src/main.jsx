import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom"
import './index.css'
import Dashboard from './Dashboard.jsx'
import Login from './Login.jsx'
import Landing from './Landing.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      {/* <nav>
        <NavLink to="/login" className="navlink primary-btn">Login</NavLink>
      </nav> */}
      <Routes>
        <Route path="/" element={<Landing />}/>
        <Route path="/dashboard" element={<Dashboard />}/>
        <Route path="/login" element={<Login />}/>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
