import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { TrendingUp, Activity, DollarSign, AlertTriangle, Play, Pause, Settings } from 'lucide-react';

// Use current hostname in dev, or the production URL in prod.
// Ideally, use VITE_API_URL environment variable.
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

export default function Dashboard() {
    const [stats, setStats] = useState(null);
    const [trades, setTrades] = useState([]);
    const [status, setStatus] = useState("ACTIVE");
    const [loading, setLoading] = useState(true);
    const [showConfig, setShowConfig] = useState(false);
    const [showHoldings, setShowHoldings] = useState(false);

    // Poll data every 5 seconds
    useEffect(() => {
        const fetchData = async () => {
            try {
                const [statsRes, tradesRes] = await Promise.all([
                    axios.get(`${API_BASE}/stats`),
                    axios.get(`${API_BASE}/trades`)
                ]);

                setStats(statsRes.data);
                setStatus(statsRes.data.settings?.status || "ACTIVE");
                setTrades(tradesRes.data);
                setLoading(false);
            } catch (error) {
                console.error("Error fetching data:", error);
                setLoading(false);
            }
        };

        fetchData();
        const interval = setInterval(fetchData, 5000);
        return () => clearInterval(interval);
    }, []);

    const toggleStatus = async () => {
        try {
            const res = await axios.post(`${API_BASE}/toggle_status`);
            setStatus(res.data.status); // Toggle API still returns { status: ... } directly usually
        } catch (error) {
            console.error("Error toggling status:", error);
        }
    };

    if (loading) return <div className="p-10 text-white">Loading Dashboard...</div>;

    return (
        <div className="min-h-screen bg-slate-900 text-slate-100 p-6 font-sans relative">
            {/* Header */}
            <header className="flex justify-between items-center mb-8">
                <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
                    AI Hedge Fund <span className="text-sm font-mono text-slate-400">Simulation v4.0</span>
                </h1>
                <div className="flex items-center gap-4">
                    <button
                        onClick={() => setShowConfig(true)}
                        className="p-2 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition"
                    >
                        <Settings size={20} />
                    </button>
                    <div className={`px-4 py-1 rounded-full text-sm font-bold ${status === 'ACTIVE' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                        {status}
                    </div>
                    <button
                        onClick={toggleStatus}
                        className={`p-2 rounded-full ${status === 'ACTIVE' ? 'bg-red-500 hover:bg-red-600' : 'bg-green-500 hover:bg-green-600'} transition`}
                    >
                        {status === 'ACTIVE' ? <Pause size={20} /> : <Play size={20} />}
                    </button>
                </div>
            </header>

            {/* Config Modal */}
            {showConfig && (
                <ConfigModal onClose={() => setShowConfig(false)} stats={stats} />
            )}

            {/* Holdings Modal */}
            {showHoldings && (
                <HoldingsModal onClose={() => setShowHoldings(false)} portfolio={stats?.portfolio || []} />
            )}

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                <StatCard
                    title="Total Equity"
                    value={`₹${stats?.total_equity?.toLocaleString() || stats?.balance?.toLocaleString()}`}
                    icon={<DollarSign className="text-green-400" />}
                    trend={(() => {
                        if (!stats?.capital || !stats?.total_equity) return null;
                        const pnl = ((stats.total_equity - stats.capital) / stats.capital) * 100;
                        return pnl > 0 ? `+${pnl.toFixed(2)}%` : `${pnl.toFixed(2)}%`;
                    })()}
                />
                <StatCard
                    title="Cash Balance"
                    value={`₹${stats?.balance?.toLocaleString()}`}
                    icon={<DollarSign className="text-blue-400" />}
                />
                <StatCard
                    title="Active Holdings"
                    value={stats?.holdings_count || 0}
                    icon={<Activity className="text-purple-400" />}
                    onClick={() => setShowHoldings(true)}
                    className="cursor-pointer hover:bg-slate-750 transition"
                />
                <StatCard
                    title="AI Risk Mode"
                    value={stats?.settings?.risk_profile || "AGGRESSIVE"}
                    icon={<AlertTriangle className="text-yellow-400" />}
                />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Main Chart Area */}
                <div className="lg:col-span-2 bg-slate-800 rounded-xl p-6 border border-slate-700">
                    <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                        <TrendingUp size={20} /> Portfolio Performance
                    </h2>
                    <div className="h-64 w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={[
                                { name: 'Start', val: stats?.capital || 100000 },
                                { name: 'Now', val: stats?.total_equity || stats?.capital || 100000 }
                            ]}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                                <XAxis dataKey="name" stroke="#94a3b8" />
                                <YAxis stroke="#94a3b8" domain={['auto', 'auto']} />
                                <Tooltip
                                    contentStyle={{ backgroundColor: '#1e293b', border: 'none' }}
                                    formatter={(value) => [`₹${value.toLocaleString()}`, 'Equity']}
                                />
                                <Line type="monotone" dataKey="val" stroke="#8b5cf6" strokeWidth={3} dot={{ r: 6 }} />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Live Feed / Trade Log */}
                <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 h-[400px] overflow-hidden flex flex-col">
                    <h2 className="text-xl font-semibold mb-4">Live AI Feed</h2>
                    <div className="overflow-y-auto flex-1 space-y-4 pr-2 custom-scrollbar">
                        {trades.map((trade, i) => (
                            <div key={i} className="bg-slate-900/50 p-3 rounded-lg border-l-4 border-blue-500">
                                <div className="flex justify-between items-start mb-1">
                                    <span className="font-bold text-blue-300">{trade.symbol}</span>
                                    <span className="text-xs text-slate-500">{new Date(trade.timestamp).toLocaleTimeString()}</span>
                                </div>
                                <div className="text-sm font-mono text-green-400">{trade.action} @ ₹{trade.price}</div>
                                <p className="text-xs text-slate-400 mt-2 italic">"{trade.ai_reason}"</p>
                            </div>
                        ))}
                        {trades.length === 0 && <div className="text-slate-500 text-center mt-10">No recent activity</div>}
                    </div>
                </div>
            </div>
        </div>
    );
}

function ConfigModal({ onClose, stats }) {
    const [balance, setBalance] = useState(stats?.balance || 10000);
    const [risk, setRisk] = useState(stats?.settings?.risk_profile || "Balanced");

    // Parse existing period (e.g. "1 Month") or default to "1 Month"
    const initialPeriod = stats?.settings?.investment_period || "1 Month";
    const [periodQty, setPeriodQty] = useState(parseInt(initialPeriod) || 1);
    // Remove plural 's' for consistency in state if present, though we will add it back mostly
    const initialUnit = initialPeriod.replace(/[0-9]/g, '').trim();
    const [periodUnit, setPeriodUnit] = useState(initialUnit || "Month");

    const [returnGoal, setReturnGoal] = useState(stats?.settings?.expected_return || 10);

    const handleSave = async () => {
        try {
            // Construct string like "6 Months"
            const combinedPeriod = `${periodQty} ${periodUnit}`;

            await axios.post(`${API_BASE}/save_settings`, {
                balance: Number(balance),
                risk,
                period: combinedPeriod,
                expected_return: Number(returnGoal)
            });
            onClose();
            window.location.reload(); // Reload to reflect changes
        } catch (error) {
            console.error("Failed to save settings", error);
        }
    }

    return (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 backdrop-blur-sm">
            <div className="bg-slate-800 p-8 rounded-2xl w-96 border border-slate-600 shadow-2xl">
                <h2 className="text-2xl font-bold mb-6 text-white text-center">Fund Configuration</h2>

                <div className="space-y-4">
                    <div>
                        <label className="block text-slate-400 text-sm mb-1">Initial Capital (₹)</label>
                        <input
                            type="number"
                            value={balance}
                            onChange={(e) => setBalance(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-white focus:outline-none focus:border-blue-500"
                        />
                    </div>

                    <div>
                        <label className="block text-slate-400 text-sm mb-1">Risk Profile</label>
                        <select
                            value={risk}
                            onChange={(e) => setRisk(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-white focus:outline-none focus:border-blue-500"
                        >
                            <option value="Conservative">Conservative (Low Risk)</option>
                            <option value="Balanced">Balanced (Medium Risk)</option>
                            <option value="Aggressive">Aggressive (High Risk)</option>
                        </select>
                    </div>

                    <div>
                        <label className="block text-slate-400 text-sm mb-1">Investment Horizon</label>
                        <div className="flex gap-2">
                            <input
                                type="number"
                                value={periodQty}
                                onChange={(e) => setPeriodQty(e.target.value)}
                                min="1"
                                placeholder="Qty"
                                className="w-1/3 bg-slate-900 border border-slate-700 rounded p-2 text-white focus:outline-none focus:border-blue-500"
                            />
                            <select
                                value={periodUnit}
                                onChange={(e) => setPeriodUnit(e.target.value)}
                                className="w-2/3 bg-slate-900 border border-slate-700 rounded p-2 text-white focus:outline-none focus:border-blue-500"
                            >
                                <option value="Days">Days</option>
                                <option value="Weeks">Weeks</option>
                                <option value="Months">Months</option>
                                <option value="Years">Years</option>
                            </select>
                        </div>
                    </div>

                    <div>
                        <label className="block text-slate-400 text-sm mb-1">Expected Return (%)</label>
                        <input
                            type="number"
                            value={returnGoal}
                            onChange={(e) => setReturnGoal(e.target.value)}
                            className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-white focus:outline-none focus:border-blue-500"
                        />
                    </div>
                </div>

                <div className="flex gap-4 mt-8">
                    <button onClick={onClose} className="flex-1 bg-slate-700 hover:bg-slate-600 py-2 rounded text-slate-300 transition">Cancel</button>
                    <button onClick={handleSave} className="flex-1 bg-blue-500 hover:bg-blue-600 py-2 rounded text-white font-bold transition">Save & Restart</button>
                </div>
            </div>
        </div>
    )
}

function StatCard({ title, value, icon, trend, onClick, className }) {
    return (
        <div
            onClick={onClick}
            className={`bg-slate-800 p-6 rounded-xl border border-slate-700 shadow-lg ${className || ''}`}
        >
            <div className="flex justify-between items-start mb-2">
                <h3 className="text-slate-400 text-sm font-medium">{title}</h3>
                {icon}
            </div>
            <div className="text-2xl font-bold text-slate-100">{value}</div>
            {trend && <div className="text-green-400 text-xs font-bold mt-1">{trend}</div>}
        </div>
    )
}

function HoldingsModal({ onClose, portfolio }) {
    return (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 backdrop-blur-sm">
            <div className="bg-slate-800 p-8 rounded-2xl w-[500px] border border-slate-600 shadow-2xl max-h-[80vh] overflow-hidden flex flex-col">
                <div className="flex justify-between items-center mb-6">
                    <h2 className="text-2xl font-bold text-white">Your Portfolio</h2>
                    <button onClick={onClose} className="text-slate-400 hover:text-white">✕</button>
                </div>

                <div className="overflow-y-auto custom-scrollbar flex-1 pr-2">
                    {portfolio.length === 0 ? (
                        <div className="text-center text-slate-500 py-10">No active holdings.</div>
                    ) : (
                        <div className="space-y-3">
                            {portfolio.map((item, i) => {
                                const isProfit = item.pnl >= 0;
                                return (
                                    <div key={i} className="bg-slate-900 p-4 rounded-lg border border-slate-700 flex justify-between items-center">
                                        <div>
                                            <div className="font-bold text-lg text-blue-300">{item.symbol}</div>
                                            <div className="text-xs text-slate-500">
                                                Buy: ₹{item.avg_price?.toFixed(2)} <span className="text-slate-600">|</span> Cur: ₹{item.current_price?.toFixed(2)}
                                            </div>
                                        </div>
                                        <div className="text-right">
                                            <div className="text-xl font-bold text-white">{item.qty} <span className="text-xs text-slate-500 font-normal">shares</span></div>
                                            {item.pnl !== undefined && (
                                                <div className={`text-xs font-bold ${isProfit ? 'text-green-400' : 'text-red-400'}`}>
                                                    {isProfit ? '+' : ''}₹{item.pnl?.toFixed(2)} ({isProfit ? '+' : ''}{item.pnl_percent?.toFixed(2)}%)
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>

                <div className="mt-6 pt-4 border-t border-slate-700">
                    <button onClick={onClose} className="w-full bg-blue-600 hover:bg-blue-700 py-2 rounded text-white font-bold transition">Close</button>
                </div>
            </div>
        </div>
    )
}
