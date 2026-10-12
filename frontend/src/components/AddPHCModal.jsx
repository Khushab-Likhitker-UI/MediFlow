import React, { useState } from 'react';
import { X, Activity, AlertCircle } from 'lucide-react';
import { API_BASE_URL } from '../config';

export const AddPHCModal = ({ onClose, onAdd }) => {
  const [name, setName] = useState('');
  const [block, setBlock] = useState('North Block');
  const [stockItems, setStockItems] = useState([
    { itemName: 'Paracetamol 500mg', currentUnits: 500, avgDailyConsumption: 100 },
    { itemName: 'Amoxicillin 250mg', currentUnits: 250, avgDailyConsumption: 50 },
    { itemName: 'ORS Packets', currentUnits: 400, avgDailyConsumption: 50 },
    { itemName: 'IV Fluids', currentUnits: 200, avgDailyConsumption: 40 },
    { itemName: 'Syringes', currentUnits: 1000, avgDailyConsumption: 150 },
    { itemName: 'Bandages', currentUnits: 300, avgDailyConsumption: 50 }
  ]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setError('');
    setLoading(true);

    const payload = {
      name: name.trim(),
      block,
      stockItems: stockItems.map(item => ({
        itemName: item.itemName,
        currentUnits: Number(item.currentUnits),
        avgDailyConsumption: Number(item.avgDailyConsumption)
      }))
    };

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/facility/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to register PHC in Supabase database.');
      }

      const savedData = await response.json();
      onAdd(savedData);
    } catch (err) {
      setError(err.message || 'Error connecting to Supabase API server.');
    } finally {
      setLoading(false);
    }
  };

  const updateItem = (index, field, value) => {
    const newItems = [...stockItems];
    newItems[index][field] = value;
    setStockItems(newItems);
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-white border-2 border-[#111] w-full max-w-2xl flex flex-col max-h-[90vh] shadow-[0_20px_50px_rgba(0,0,0,0.2)]">
        
        <div className="flex items-center justify-between px-8 py-6 border-b-2 border-[#111]">
          <h2 className="text-lg font-bold tracking-[0.15em] uppercase text-[#111]">Register New PHC (Supabase DB)</h2>
          <button 
            onClick={onClose}
            className="text-gray-400 hover:text-[#111] transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col flex-1 overflow-hidden">
          <div className="p-8 overflow-y-auto">
            {error && (
              <div className="mb-6 p-3 bg-red-50 border border-red-300 text-red-700 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 text-red-500" />
                <span>{error}</span>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
              <div>
                <label className="block text-[10px] uppercase tracking-[0.1em] text-gray-500 mb-2">PHC Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={e => setName(e.target.value)}
                  className="w-full border-b-2 border-gray-200 py-2 focus:outline-none focus:border-[#111] text-sm font-medium transition-colors"
                  placeholder="e.g. Central Clinic"
                />
              </div>
              <div>
                <label className="block text-[10px] uppercase tracking-[0.1em] text-gray-500 mb-2">Block</label>
                <select
                  value={block}
                  onChange={e => setBlock(e.target.value)}
                  className="w-full border-b-2 border-gray-200 py-2 focus:outline-none focus:border-[#111] text-sm font-medium transition-colors uppercase tracking-wider"
                >
                  <option value="North Block">North Block</option>
                  <option value="South Block">South Block</option>
                  <option value="East Block">East Block</option>
                  <option value="West Block">West Block</option>
                </select>
              </div>
            </div>

            <div>
              <h3 className="text-xs font-bold uppercase tracking-[0.1em] text-[#111] mb-4">Initial Stock Levels</h3>
              <div className="space-y-4">
                {stockItems.map((item, idx) => (
                  <div key={idx} className="flex items-center gap-4 bg-gray-50 p-4 border border-gray-100">
                    <div className="w-1/3 text-sm font-medium">{item.itemName}</div>
                    <div className="flex-1">
                      <label className="block text-[9px] uppercase tracking-wider text-gray-400 mb-1">Current Units</label>
                      <input
                        type="number"
                        min="0"
                        required
                        value={item.currentUnits}
                        onChange={e => updateItem(idx, 'currentUnits', e.target.value)}
                        className="w-full border-b border-gray-300 bg-transparent py-1 text-sm focus:outline-none focus:border-[#111]"
                      />
                    </div>
                    <div className="flex-1">
                      <label className="block text-[9px] uppercase tracking-wider text-gray-400 mb-1">Daily Avg</label>
                      <input
                        type="number"
                        min="1"
                        required
                        value={item.avgDailyConsumption}
                        onChange={e => updateItem(idx, 'avgDailyConsumption', e.target.value)}
                        className="w-full border-b border-gray-300 bg-transparent py-1 text-sm focus:outline-none focus:border-[#111]"
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="p-6 border-t-2 border-[#111] bg-gray-50 flex justify-end gap-4">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-6 py-3 text-xs font-bold uppercase tracking-[0.15em] text-gray-500 hover:text-[#111] transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-8 py-3 bg-[#111] text-white text-xs font-bold uppercase tracking-[0.15em] hover:bg-black transition-colors flex items-center gap-2 cursor-pointer disabled:opacity-50"
            >
              {loading && <Activity className="w-4 h-4 animate-spin" />}
              <span>Save to Supabase DB</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
