import React, { useState } from 'react';
import axios from 'axios';

export default function Home() {
  const [url, setUrl] = useState('');
  const [query, setQuery] = useState('Get all emails and images');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleExtract = async () => {
    setLoading(true);
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
    setLoading(false);
  };

  return (
    <div style={{ maxWidth: 600, margin: '40px auto', fontFamily: 'sans-serif' }}>
      <h1>Universal Data Extractor</h1>
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
      <button onClick={handleExtract} disabled={loading || !url} style={{ padding: '10px 20px', fontSize: 16 }}>
        {loading ? 'Extracting...' : 'Extract Data'}
      </button>
      {result && (
        <div style={{ marginTop: 32 }}>
          <h2>Results</h2>
          <pre style={{ background: '#f4f4f4', padding: 16, borderRadius: 8 }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
