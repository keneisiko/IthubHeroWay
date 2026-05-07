import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Main from './pages/Main';
function App() {
  return (
    <BrowserRouter>
        <Routes>
			<Route path="/" element={<Main />} />
			<Route path="/Main" element={<Main />} />
        </Routes>
    </BrowserRouter>
  );
}
export default App;