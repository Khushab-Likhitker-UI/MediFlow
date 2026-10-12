import React, { useState, useEffect } from 'react';
import { enqueueOperation, getCachedMedicines, getAllSyncItems } from '../db/indexedDB';
import { syncQueue, fetchAndCacheCatalogue } from '../services/syncService';
import { Pill, Bed, Users, CheckCircle2, AlertCircle, Clock, ArrowRight, Database } from 'lucide-react';

const FALLBACK_MEDICINE_LIST = [
  { name: "Paracetamol 500mg", unit: "tablets", category: "Analgesic" },
  { name: "Amoxicillin 250mg", unit: "capsules", category: "Antibiotic" },
  { name: "ORS Packets", unit: "sachets", category: "Electrolyte" },
  { name: "Anti-venom", unit: "vials", category: "Antidote" },
  { name: "IV Fluids", unit: "bags", category: "Fluid" },
  { name: "Syringes", unit: "units", category: "Consumable" },
  { name: "Bandages", unit: "rolls", category: "Consumable" },
  { name: "Ibuprofen 400mg", unit: "tablets", category: "Analgesic" },
  { name: "N95 Respirator Mask", unit: "units", category: "PPE" },
  { name: "Nitrile Exam Gloves", unit: "boxes", category: "PPE" },
  { name: "Azithromycin 500mg", unit: "tablets", category: "Antibiotic" },
  { name: "Ciprofloxacin 500mg", unit: "tablets", category: "Antibiotic" },
  { name: "Metformin 500mg", unit: "tablets", category: "Antidiabetic" },
  { name: "Amlodipine 10mg", unit: "tablets", category: "Cardiovascular" },
  { name: "Insulin Glargine", unit: "vials", category: "Antidiabetic" },
  { name: "Omeprazole 20mg", unit: "capsules", category: "Gastrointestinal" },
  { name: "Cetirizine 10mg", unit: "tablets", category: "Antihistamine" },
  { name: "Losartan 50mg", unit: "tablets", category: "Cardiovascular" },
  { name: "Atorvastatin 20mg", unit: "tablets", category: "Cardiovascular" },
  { name: "Albuterol Inhaler", unit: "units", category: "Respiratory" },
  { name: "Ceftriaxone 1g", unit: "vials", category: "Antibiotic" },
  { name: "Morphine 10mg", unit: "vials", category: "Analgesic" },
  { name: "Dexamethasone 4mg", unit: "tablets", category: "Corticosteroid" },
  { name: "Epinephrine Auto-injector", unit: "units", category: "Emergency" },
  { name: "Hydrocortisone Cream", unit: "tubes", category: "Topical" }
];

export default function Forms({ phcId, isOnline, onSyncTrigger }) {
  const [updateType, setUpdateType] = useState('Medicine'); // Medicine, Beds, Attendance
  const [movementType, setMovementType] = useState('adjusted'); // adjusted, received, dispensed
  const [medicines, setMedicines] = useState(FALLBACK_MEDICINE_LIST);
  const [selectedMedName, setSelectedMedName] = useState(FALLBACK_MEDICINE_LIST[0].name);
  const [batchNumber, setBatchNumber] = useState('DEFAULT_BATCH');
  const [catalogueCachedAt, setCatalogueCachedAt] = useState(null);
  const [quantity, setQuantity] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('success');
  const [lastOpId, setLastOpId] = useState(null);
  const [hasPendingItems, setHasPendingItems] = useState(false);

  // Load medicines from cache or live API
  const loadCatalogue = React.useCallback(async () => {
    try {
      if (isOnline) {
        await fetchAndCacheCatalogue();
      }
      const cached = await getCachedMedicines();
      if (cached && cached.medicines && cached.medicines.length > 0) {
        setMedicines(cached.medicines);
        setCatalogueCachedAt(cached.cachedAt);
        if (!cached.medicines.some((m) => m.name === selectedMedName)) {
          setSelectedMedName(cached.medicines[0].name);
        }
      }
    } catch {
      // Keep fallback list
    }
  }, [isOnline, selectedMedName]);

  const checkPending = React.useCallback(async () => {
    const items = await getAllSyncItems();
    setHasPendingItems(items.some((i) => i.sync_state !== 'synced'));
  }, []);

  useEffect(() => {
    loadCatalogue();
    checkPending();
  }, [loadCatalogue, checkPending]);

  const selectedMedicineObj = medicines.find((m) => m.name === selectedMedName) || medicines[0];
  const currentBaseUnit = updateType === 'Medicine'
    ? (selectedMedicineObj?.unit || 'units')
    : updateType === 'Beds'
    ? 'beds'
    : 'doctors';

  const handleSubmit = async (e) => {
    e.preventDefault();

    const parsedQty = Number(quantity);
    if (quantity === '' || isNaN(parsedQty) || parsedQty < 0 || !Number.isInteger(parsedQty)) {
      setMessage('Please enter a valid non-negative integer quantity.');
      setMessageType('error');
      return;
    }

    if (!phcId) {
      setMessage('Please select a facility before logging updates.');
      setMessageType('error');
      return;
    }

    setLoading(true);
    setMessage('');

    try {
      // 1. Create stable operation payload according to domain model and API contract
      const eventTime = new Date().toISOString();
      const payload = {
        facility: phcId,
        phc_id: phcId,
        update_type: updateType,
        movement_type: movementType,
        occurred_at: eventTime,
        timestamp: eventTime,
        unit: currentBaseUnit,
      };

      if (updateType === 'Medicine') {
        payload.medicine = selectedMedName;
        payload.medicine_name = selectedMedName;
        payload.batch_number = batchNumber.trim() || 'DEFAULT_BATCH';
        payload.quantity = parsedQty;
      } else if (updateType === 'Beds') {
        payload.available_beds = parsedQty;
        payload.quantity = parsedQty;
      } else if (updateType === 'Attendance') {
        payload.doctors_present = parsedQty;
        payload.quantity = parsedQty;
      }

      // 2. Persist durably in IndexedDB BEFORE attempting any network delivery
      const enqueued = await enqueueOperation(payload);
      setLastOpId(enqueued.client_operation_id);

      const itemDesc = updateType === 'Medicine'
        ? `${parsedQty} ${currentBaseUnit} of ${selectedMedName} (${movementType})`
        : updateType === 'Beds'
        ? `${parsedQty} available beds`
        : `${parsedQty} doctors on duty`;

      setQuantity('');

      // 3. If online, attempt immediate sync; if offline, inform user clearly
      if (isOnline) {
        await syncQueue();
        if (onSyncTrigger) onSyncTrigger();

        const allItems = await getAllSyncItems();
        const currentItem = allItems.find((i) => i.client_operation_id === enqueued.client_operation_id);

        if (currentItem && currentItem.sync_state === 'synced') {
          setMessage(`Acknowledged by server: ${itemDesc}`);
          setMessageType('success');
        } else if (currentItem && currentItem.sync_state === 'needs_correction') {
          setMessage(`Requires correction: ${currentItem.error_message || 'Validation error'}`);
          setMessageType('error');
        } else {
          setMessage(`Enqueued locally (${enqueued.client_operation_id.slice(0, 8)}...). Transmitting in background.`);
          setMessageType('warning');
        }
      } else {
        setMessage(`Saved locally in durable outbox. Will sync automatically when network reconnects.`);
        setMessageType('warning');
      }

      await checkPending();
    } catch (err) {
      console.error('Failed to enqueue outbox operation:', err);
      setMessage('Error saving outbox record to IndexedDB: ' + err.message);
      setMessageType('error');
    } finally {
      setLoading(false);
      setTimeout(() => setMessage(''), 6000);
    }
  };

  return (
    <div className="bg-[#111111] text-white rounded-lg shadow-2xl p-6 sm:p-8 border border-neutral-800 relative overflow-hidden">
      {/* Top Banner / Title */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-6 border-b border-neutral-800 mb-6">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-400 flex items-center gap-2">
            <span>Durable Outbox Interface</span>
            <span className="w-1.5 h-1.5 rounded-full bg-red-500"></span>
          </div>
          <h2 className="text-xl sm:text-2xl font-black uppercase tracking-wider text-white mt-1 flex items-center gap-3">
            {updateType === 'Medicine' && <Pill className="w-6 h-6 text-red-500 shrink-0" />}
            {updateType === 'Beds' && <Bed className="w-6 h-6 text-cyan-400 shrink-0" />}
            {updateType === 'Attendance' && <Users className="w-6 h-6 text-emerald-400 shrink-0" />}
            <span>Log {updateType} Movement</span>
          </h2>
        </div>

        {hasPendingItems && (
          <div className="px-3 py-1.5 bg-amber-950/80 border border-amber-500/50 rounded text-amber-300 text-[10px] font-mono uppercase font-bold flex items-center gap-2">
            <Clock className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
            <span>Local Outbox Pending</span>
          </div>
        )}
      </div>

      {/* Tab Switcher */}
      <div className="grid grid-cols-3 gap-2 sm:gap-4 mb-8">
        {[
          { id: 'Medicine', label: 'Medicine Stock', icon: Pill, color: 'text-red-500', border: 'border-red-500' },
          { id: 'Beds', label: 'Bed Capacity', icon: Bed, color: 'text-cyan-400', border: 'border-cyan-400' },
          { id: 'Attendance', label: 'Doctor Roster', icon: Users, color: 'text-emerald-400', border: 'border-emerald-400' },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = updateType === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => {
                setUpdateType(tab.id);
                setQuantity('');
                setMessage('');
              }}
              className={`p-4 rounded border-2 transition-all flex flex-col items-center justify-center gap-2 cursor-pointer font-sans ${
                isActive
                  ? `bg-neutral-900 ${tab.border} shadow-[0_0_15px_rgba(255,255,255,0.05)]`
                  : 'bg-[#0a0a0a] border-neutral-800 text-neutral-500 hover:border-neutral-700 hover:text-neutral-300'
              }`}
            >
              <Icon className={`w-5 h-5 ${isActive ? tab.color : 'text-neutral-500'}`} />
              <span className={`text-xs font-bold uppercase tracking-wider ${isActive ? 'text-white' : ''}`}>
                {tab.label}
              </span>
            </button>
          );
        })}
      </div>

      {/* Status Banner */}
      {message && (
        <div
          className={`mb-6 p-4 rounded border text-xs flex items-center gap-3 animate-fade-in font-mono ${
            messageType === 'success'
              ? 'bg-emerald-950/80 border-emerald-500/60 text-emerald-300'
              : messageType === 'warning'
              ? 'bg-amber-950/80 border-amber-500/60 text-amber-300'
              : 'bg-red-950/80 border-red-500/60 text-red-300'
          }`}
        >
          {messageType === 'success' && <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />}
          {messageType === 'warning' && <Clock className="w-4 h-4 text-amber-400 shrink-0" />}
          {messageType === 'error' && <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />}
          <div className="flex-1">
            <p>{message}</p>
            {lastOpId && (
              <p className="text-[10px] text-neutral-400 font-mono mt-1">Operation ID: {lastOpId}</p>
            )}
          </div>
        </div>
      )}

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        {updateType === 'Medicine' && (
          <>
            <div>
              <div className="flex justify-between items-center mb-2.5">
                <label className="block text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-400">
                  Select Medicine / Consumable
                </label>
                {catalogueCachedAt && (
                  <span className="text-[10px] text-neutral-500 font-mono flex items-center gap-1">
                    <Database className="w-3 h-3" />
                    Cached {new Date(catalogueCachedAt).toLocaleTimeString()}
                    {!isOnline && <span className="text-amber-400 font-semibold">(Offline cache)</span>}
                  </span>
                )}
              </div>
              <select
                value={selectedMedName}
                onChange={(e) => setSelectedMedName(e.target.value)}
                className="w-full bg-[#0a0a0a] border border-neutral-700 hover:border-neutral-500 focus:border-red-500 px-4 py-3.5 rounded text-xs text-white font-mono uppercase font-bold focus:outline-none transition-colors cursor-pointer"
              >
                {medicines.map((item) => (
                  <option key={item.name} value={item.name} className="bg-[#111111] text-white py-1">
                    {item.name} [{item.unit || 'units'}]
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-400 mb-2.5">
                  Movement Type
                </label>
                <select
                  value={movementType}
                  onChange={(e) => setMovementType(e.target.value)}
                  className="w-full bg-[#0a0a0a] border border-neutral-700 focus:border-white px-4 py-3 text-xs font-mono text-white rounded focus:outline-none uppercase"
                >
                  <option value="adjusted">Adjusted / Stock Count</option>
                  <option value="received">Stock Received</option>
                  <option value="dispensed">Stock Dispensed</option>
                </select>
              </div>

              <div>
                <label className="block text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-400 mb-2.5">
                  Batch Number (Optional)
                </label>
                <input
                  type="text"
                  value={batchNumber}
                  onChange={(e) => setBatchNumber(e.target.value)}
                  placeholder="DEFAULT_BATCH"
                  className="w-full bg-[#0a0a0a] border border-neutral-700 focus:border-white px-4 py-3 text-xs font-mono text-white rounded focus:outline-none uppercase"
                />
              </div>
            </div>
          </>
        )}

        <div>
          <label className="block text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-400 mb-2.5">
            {updateType === 'Medicine'
              ? `Base-Unit Quantity (${currentBaseUnit.toUpperCase()})`
              : updateType === 'Beds'
              ? 'Total Available Vacant Beds'
              : 'Number of Doctors Currently Present on Duty'}
          </label>
          <div className="relative">
            <input
              type="number"
              min="0"
              step="1"
              required
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              placeholder="e.g., 500"
              className="w-full bg-[#0a0a0a] border border-neutral-700 focus:border-white px-4 py-3.5 text-sm font-mono text-white placeholder-neutral-600 rounded focus:outline-none transition-colors"
            />
            <div className="absolute inset-y-0 right-0 pr-4 flex items-center pointer-events-none text-neutral-400 text-xs font-mono uppercase font-bold">
              {currentBaseUnit}
            </div>
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full py-4 bg-white hover:bg-neutral-200 text-[#111111] font-black text-xs uppercase tracking-[0.25em] transition-all rounded shadow-[0_0_20px_rgba(255,255,255,0.15)] flex items-center justify-center gap-3 cursor-pointer disabled:opacity-50 mt-4"
        >
          {loading ? (
            <span>PERSISTING TO OUTBOX...</span>
          ) : (
            <>
              <span>Log Movement & Transmit</span>
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>
      </form>
    </div>
  );
}
