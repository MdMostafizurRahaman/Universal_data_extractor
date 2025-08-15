import React, { useState } from 'react';
import axios from 'axios';

export default function Home() {
  const [url, setUrl] = useState('');
  const [query, setQuery] = useState('Get all emails and images');
  const [result, setResult] = useState(null);
  const [loadingExtract, setLoadingExtract] = useState(false);
  const [loadingProfile, setLoadingProfile] = useState(false);
  const [profileUrl, setProfileUrl] = useState('');
  const [excelLink, setExcelLink] = useState('');
  const handleProfileExtract = async () => {
    setLoadingProfile(true);
    setExcelLink('');
    try {
      const res = await axios.post('http://localhost:8000/profile_excel', {
        url: profileUrl
      });
      if (res.data && res.data.excel_url) {
        setExcelLink(res.data.excel_url);
      } else {
        setExcelLink('Excel creation failed.');
      }
    } catch (err) {
      setExcelLink('Excel creation failed.');
    }
    setLoadingProfile(false);
  }

  const handleExtract = async () => {
    setLoadingExtract(true);
    // For demo, map query to data_types. In production, use AI query layer.
    let data_types = [];
    if (query.toLowerCase().includes('email')) data_types.push('emails');
    if (query.toLowerCase().includes('image')) data_types.push('images');
    if (query.toLowerCase().includes('table')) data_types.push('tables');
    if (data_types.length === 0) data_types = ['emails', 'images', 'tables'];
    try {
      const res = await axios.post('http://localhost:8000/extract', {
        url,
        data_types
      });
      setResult(res.data.result);
    } catch (err) {
      setResult({ error: 'Extraction failed.' });
    }
    setLoadingExtract(false);
  };

  return (
    <div style={{ maxWidth: 600, margin: '40px auto', fontFamily: 'sans-serif' }}>
      <h1>Universal Data Extractor</h1>
      {/* Existing Extractor UI */}
      <input
        type="text"
        placeholder="Enter page URL"
        value={url}
        onChange={e => setUrl(e.target.value)}
        style={{ width: '100%', padding: 8, marginBottom: 12 }}
      />
      <input
        type="text"
        placeholder="What data do you want? (e.g. Get all emails and images)"
        value={query}
        onChange={e => setQuery(e.target.value)}
        style={{ width: '100%', padding: 8, marginBottom: 12 }}
      />
      <button onClick={handleExtract} disabled={loadingExtract || !url} style={{ padding: '10px 20px', fontSize: 16 }}>
        {loadingExtract ? 'Extracting...' : 'Extract Data'}
      </button>
      {result && (
        <div style={{ marginTop: 32 }}>
          <h2>Results</h2>
          <pre style={{ background: '#f4f4f4', padding: 16, borderRadius: 8 }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
      {/* New Profile Extractor and PDF Maker UI */}
      <hr style={{ margin: '32px 0' }} />
  <h2>Profile Extractor and Excel Maker</h2>
      <input
        type="text"
        placeholder="Enter profile page URL"
        value={profileUrl}
        onChange={e => setProfileUrl(e.target.value)}
        style={{ width: '100%', padding: 8, marginBottom: 12 }}
      />
      <button onClick={handleProfileExtract} disabled={loadingProfile || !profileUrl} style={{ padding: '10px 20px', fontSize: 16, background: '#4f8cff', color: 'white', marginBottom: 12 }}>
        {loadingProfile ? 'Processing...' : 'Extract Profiles & Make Excel'}
      </button>
      {excelLink && (
        <div style={{ marginTop: 16 }}>
          {excelLink.startsWith('/static') ? (
            <a href={excelLink} target="_blank" rel="noopener noreferrer" style={{ color: '#4f8cff', fontWeight: 'bold' }}>Download Excel</a>
          ) : (
            <span style={{ color: 'red' }}>{excelLink}</span>
          )}
        </div>
      )}
    </div>
  );
}
