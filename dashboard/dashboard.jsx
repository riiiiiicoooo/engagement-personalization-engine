/**
 * Engagement & Personalization Engine - React Dashboard
 * ======================================================
 *
 * A 3-tab dashboard showing:
 * 1. Engagement Overview - cohort funnel with transition rates and 12-week trends
 * 2. Experiments - active A/B tests with sequential analysis progress and guardrails
 * 3. Recommendations - personalized content feed with relevance scoring
 *
 * Uses React + Recharts for visualization.
 * All data is synthetic and tells a coherent 12-week growth story.
 *
 * Dependencies:
 *   - react
 *   - recharts
 *   - react-icons (for icons)
 *
 * To use in production:
 *   - Replace synthetic data with real API calls
 *   - Connect to feature store (Feast) for feature data
 *   - Wire experiment API for real experiment data
 *   - Integrate with recommendation engine for real personalization
 */

import React, { useState } from 'react';
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  ComposedChart, ScatterChart, Scatter
} from 'recharts';
import { TrendingUp, AlertCircle, CheckCircle } from 'react-icons/fa';

/**
 * Engagement & Personalization Dashboard
 *
 * A comprehensive view into user engagement, experiments, and personalization.
 * Shows 12-week progression with realistic metrics and a coherent story.
 */
const Dashboard = () => {
  const [activeTab, setActiveTab] = useState('engagement');

  // =========================================================================
  // SECTION 1: ENGAGEMENT OVERVIEW
  // =========================================================================

  // Cohort funnel data - 12 week progression
  const cohortFunnelData = [
    {
      week: 1,
      Thriving: 15.2,
      Engaged: 28.3,
      Drifting: 35.1,
      'At-Risk': 12.4,
      Dormant: 9.0
    },
    {
      week: 2,
      Thriving: 16.8,
      Engaged: 29.5,
      Drifting: 33.8,
      'At-Risk': 11.7,
      Dormant: 8.2
    },
    {
      week: 3,
      Thriving: 18.2,
      Engaged: 31.1,
      Drifting: 32.0,
      'At-Risk': 10.9,
      Dormant: 7.8
    },
    {
      week: 4,
      Thriving: 19.5,
      Engaged: 32.3,
      Drifting: 30.5,
      'At-Risk': 10.2,
      Dormant: 7.5
    },
    {
      week: 5,
      Thriving: 21.2,
      Engaged: 33.8,
      Drifting: 28.9,
      'At-Risk': 9.6,
      Dormant: 6.5
    },
    {
      week: 6,
      Thriving: 22.5,
      Engaged: 34.9,
      Drifting: 27.8,
      'At-Risk': 9.1,
      Dormant: 5.7
    },
    {
      week: 7,
      Thriving: 24.1,
      Engaged: 35.8,
      Drifting: 26.2,
      'At-Risk': 8.5,
      Dormant: 5.4
    },
    {
      week: 8,
      Thriving: 25.8,
      Engaged: 36.9,
      Drifting: 24.8,
      'At-Risk': 7.9,
      Dormant: 4.6
    },
    {
      week: 9,
      Thriving: 27.3,
      Engaged: 37.5,
      Drifting: 23.2,
      'At-Risk': 7.4,
      Dormant: 4.6
    },
    {
      week: 10,
      Thriving: 28.7,
      Engaged: 38.2,
      Drifting: 21.8,
      'At-Risk': 6.9,
      Dormant: 4.4
    },
    {
      week: 11,
      Thriving: 29.8,
      Engaged: 38.8,
      Drifting: 20.9,
      'At-Risk': 6.4,
      Dormant: 4.1
    },
    {
      week: 12,
      Thriving: 30.6,
      Engaged: 39.2,
      Drifting: 20.1,
      'At-Risk': 6.2,
      Dormant: 3.9
    }
  ];

  // Cohort transition rates
  const transitionRates = [
    { from: 'Thriving', to: 'Engaged', rate: '3.2%' },
    { from: 'Engaged', to: 'Drifting', rate: '8.1%' },
    { from: 'Drifting', to: 'At-Risk', rate: '12.5%' },
    { from: 'At-Risk', to: 'Dormant', rate: '18.3%' },
    { from: 'Drifting', to: 'Thriving', rate: '6.2%' },
    { from: 'At-Risk', to: 'Engaged', rate: '24.1%' }
  ];

  // Churn rate by cohort (week 12)
  const churnByCohor t = [
    { cohort: 'Thriving', churnRate: 2.1, count: 3060 },
    { cohort: 'Engaged', churnRate: 8.2, count: 3920 },
    { cohort: 'Drifting', churnRate: 42.3, count: 2010 },
    { cohort: 'At-Risk', churnRate: 71.4, count: 620 },
    { cohort: 'Dormant', churnRate: 88.9, count: 390 }
  ];

  // =========================================================================
  // SECTION 2: EXPERIMENTS
  // =========================================================================

  const experimentsData = [
    {
      id: 'exp-042',
      name: 'Progress Indicators v2',
      status: 'running',
      sampleSize: 94660,
      control: { rate: 44.8, users: 47460 },
      treatment: { rate: 48.6, users: 47200 },
      lift: 8.6,
      pValue: 0.000001,
      infoFraction: 0.85,
      sequential: {
        boundary: 0.0236,
        pValue: 0.000001,
        canStop: true
      },
      guardrails: [
        { metric: 'session_duration', value: -4.2, threshold: -10.0, status: 'ok' },
        { metric: 'crash_rate', value: 0.05, threshold: 0.5, status: 'ok' }
      ]
    },
    {
      id: 'exp-043',
      name: 'Personalized Workout Plans',
      status: 'running',
      sampleSize: 156300,
      control: { rate: 52.1, users: 78150 },
      treatment: { rate: 56.2, users: 78150 },
      lift: 7.9,
      pValue: 0.004,
      infoFraction: 0.65,
      sequential: {
        boundary: 0.0056,
        pValue: 0.004,
        canStop: false
      },
      guardrails: [
        { metric: 'retention_7d', value: 2.3, threshold: -5.0, status: 'ok' },
        { metric: 'notification_opt_out', value: 1.2, threshold: 2.0, status: 'ok' }
      ]
    },
    {
      id: 'exp-040',
      name: 'Social Challenges',
      status: 'completed',
      sampleSize: 102400,
      control: { rate: 38.5, users: 51200 },
      treatment: { rate: 39.2, users: 51200 },
      lift: 1.8,
      pValue: 0.187,
      decision: 'ITERATE',
      guardrails: [
        { metric: 'session_duration', value: -2.1, threshold: -10.0, status: 'ok' },
        { metric: 'crash_rate', value: -0.02, threshold: 0.5, status: 'ok' }
      ]
    }
  ];

  // Sequential analysis visualization (for first experiment)
  const sequentialData = [
    { fraction: 0.25, boundary: 0.000088, pValue: 0.000001, label: 'Week 1' },
    { fraction: 0.5, boundary: 0.005564, pValue: 0.000001, label: 'Week 2' },
    { fraction: 0.75, boundary: 0.023594, pValue: 0.000001, label: 'Week 3' },
    { fraction: 0.85, boundary: 0.031204, pValue: 0.000001, label: 'Today' }
  ];

  // =========================================================================
  // SECTION 3: RECOMMENDATIONS
  // =========================================================================

  const userProfile = {
    userId: 'user_4521',
    cohort: 'Engaged',
    engagementScore: 79.2,
    lastActive: '2 hours ago',
    goals: ['Weight Loss', 'Build Strength'],
    favoriteCategories: ['Cardio', 'Strength Training', 'Nutrition']
  };

  const recommendations = [
    {
      id: 'rec-1',
      type: 'workout',
      title: 'HIIT Circuit: 20 Minutes',
      description: 'Combine cardio bursts with strength moves to maximize calories',
      relevance: 0.94,
      reason: 'Matches weight loss goals + strength interest',
      category: 'Cardio',
      difficulty: 'Intermediate'
    },
    {
      id: 'rec-2',
      type: 'article',
      title: 'Nutrition Timing for Maximum Gains',
      description: 'When to eat carbs, protein, and fats for optimal results',
      relevance: 0.87,
      reason: 'Complements your recent strength training sessions',
      category: 'Nutrition',
      difficulty: 'Intermediate'
    },
    {
      id: 'rec-3',
      type: 'challenge',
      title: '7-Day Core Strength Challenge',
      description: 'Progressive core work with friends in your network',
      relevance: 0.82,
      reason: 'Social engagement + strength goals + 7-day pattern fit',
      category: 'Strength',
      difficulty: 'Intermediate'
    },
    {
      id: 'rec-4',
      type: 'workout',
      title: 'Morning Energy Flow: 15 Minutes',
      description: 'Dynamic mobility + light cardio to start your day',
      relevance: 0.76,
      reason: 'Perfect for your typical 6am active window',
      category: 'Cardio',
      difficulty: 'Beginner'
    },
    {
      id: 'rec-5',
      type: 'article',
      title: 'Recovery: Why Rest Days Matter',
      description: 'How active recovery improves performance and prevents injury',
      relevance: 0.71,
      reason: 'You\'ve completed 5 consecutive days - recovery insight may help',
      category: 'Wellness',
      difficulty: 'Advanced'
    }
  ];

  // =========================================================================
  // RENDER FUNCTIONS
  // =========================================================================

  const renderEngagementTab = () => (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h2 className="text-2xl font-bold mb-2">Engagement Overview</h2>
          <p className="text-gray-600">12-week progression of user cohort distribution</p>
        </div>
        <div className="text-right">
          <p className="text-3xl font-bold text-green-600">+60.1%</p>
          <p className="text-sm text-gray-600">healthy users (Thriving + Engaged)</p>
        </div>
      </div>

      {/* Cohort Stacked Area Chart */}
      <div className="bg-white p-4 rounded-lg border border-gray-200">
        <h3 className="text-lg font-semibold mb-4">Cohort Distribution Over 12 Weeks</h3>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={cohortFunnelData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="week" label={{ value: 'Week', position: 'insideBottomRight', offset: -5 }} />
            <YAxis label={{ value: 'Percentage of Users', angle: -90, position: 'insideLeft' }} />
            <Tooltip formatter={(value) => `${value.toFixed(1)}%`} />
            <Legend />
            <Line type="monotone" dataKey="Thriving" stroke="#10b981" strokeWidth={2} />
            <Line type="monotone" dataKey="Engaged" stroke="#3b82f6" strokeWidth={2} />
            <Line type="monotone" dataKey="Drifting" stroke="#f59e0b" strokeWidth={2} />
            <Line type="monotone" dataKey="At-Risk" stroke="#ef4444" strokeWidth={2} />
            <Line type="monotone" dataKey="Dormant" stroke="#6b7280" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Transition Rates */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white p-4 rounded-lg border border-gray-200">
          <h3 className="text-lg font-semibold mb-4">Cohort Transition Rates</h3>
          <div className="space-y-3">
            {transitionRates.map((t, idx) => (
              <div key={idx} className="flex justify-between items-center py-2 border-b">
                <span className="text-sm">{t.from} → {t.to}</span>
                <span className="font-semibold text-blue-600">{t.rate}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 30-Day Churn by Cohort */}
        <div className="bg-white p-4 rounded-lg border border-gray-200">
          <h3 className="text-lg font-semibold mb-4">30-Day Churn Rate by Cohort</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={churnByCohort}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="cohort" />
              <YAxis label={{ value: 'Churn %', angle: -90, position: 'insideLeft' }} />
              <Tooltip formatter={(value) => `${value.toFixed(1)}%`} />
              <Bar dataKey="churnRate" fill="#ef4444" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-gradient-to-r from-green-50 to-green-100 p-4 rounded-lg border border-green-200">
          <p className="text-sm text-gray-600 mb-1">Thriving Users (Week 12)</p>
          <p className="text-3xl font-bold text-green-700">3,060</p>
          <p className="text-xs text-green-600 mt-1">+100% since week 1</p>
        </div>
        <div className="bg-gradient-to-r from-blue-50 to-blue-100 p-4 rounded-lg border border-blue-200">
          <p className="text-sm text-gray-600 mb-1">Avg Engagement Score</p>
          <p className="text-3xl font-bold text-blue-700">62.4</p>
          <p className="text-xs text-blue-600 mt-1">+8.3 points since week 1</p>
        </div>
        <div className="bg-gradient-to-r from-purple-50 to-purple-100 p-4 rounded-lg border border-purple-200">
          <p className="text-sm text-gray-600 mb-1">90-Day Retention</p>
          <p className="text-3xl font-bold text-purple-700">51%</p>
          <p className="text-xs text-purple-600 mt-1">+59% improvement</p>
        </div>
      </div>
    </div>
  );

  const renderExperimentsTab = () => (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold mb-2">Active Experiments</h2>
        <p className="text-gray-600">Real-time monitoring with sequential analysis</p>
      </div>

      {/* Sequential Analysis Chart */}
      <div className="bg-white p-4 rounded-lg border border-gray-200">
        <h3 className="text-lg font-semibold mb-4">Sequential Analysis: exp-042</h3>
        <p className="text-sm text-gray-600 mb-4">O'Brien-Fleming Spending Boundary</p>
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={sequentialData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="label" />
            <YAxis scale="log" domain={[0.00001, 1]} label={{ value: 'p-value (log scale)', angle: -90, position: 'insideLeft' }} />
            <Tooltip formatter={(value) => value.toFixed(6)} />
            <Legend />
            <Line type="monotone" dataKey="boundary" stroke="#ef4444" strokeWidth={2} name="Sequential Boundary" />
            <Scatter dataKey="pValue" fill="#3b82f6" name="Observed p-value" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Experiments List */}
      <div className="space-y-4">
        {experimentsData.map((exp) => (
          <div key={exp.id} className="bg-white p-4 rounded-lg border border-gray-200">
            <div className="flex justify-between items-start mb-3">
              <div>
                <h3 className="text-lg font-semibold">{exp.name}</h3>
                <p className="text-sm text-gray-600">{exp.id}</p>
              </div>
              <div className="flex gap-2">
                <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
                  exp.status === 'running' ? 'bg-blue-100 text-blue-800' :
                  exp.status === 'completed' ? 'bg-green-100 text-green-800' : ''
                }`}>
                  {exp.status.charAt(0).toUpperCase() + exp.status.slice(1)}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <p className="text-sm text-gray-600">Control</p>
                <p className="text-2xl font-bold">{exp.control.rate.toFixed(1)}%</p>
                <p className="text-xs text-gray-500">{exp.control.users.toLocaleString()} users</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Treatment</p>
                <p className="text-2xl font-bold">{exp.treatment.rate.toFixed(1)}%</p>
                <p className="text-xs text-gray-500">{exp.treatment.users.toLocaleString()} users</p>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4 mb-4 pb-4 border-b">
              <div>
                <p className="text-sm text-gray-600">Lift</p>
                <p className={`text-2xl font-bold ${exp.lift > 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {exp.lift > 0 ? '+' : ''}{exp.lift.toFixed(1)}%
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600">P-value</p>
                <p className="text-2xl font-bold text-blue-600">{exp.pValue.toFixed(6)}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Sample Size</p>
                <p className="text-2xl font-bold">{(exp.sampleSize / 1000).toFixed(0)}K</p>
              </div>
            </div>

            {/* Guardrails */}
            <div>
              <p className="text-sm font-semibold mb-2">Guardrails</p>
              <div className="space-y-1">
                {exp.guardrails.map((g, idx) => (
                  <div key={idx} className="flex justify-between items-center text-sm">
                    <span className="text-gray-700">{g.metric}</span>
                    <div className="flex items-center gap-2">
                      <span className={`${g.value < g.threshold ? 'text-red-600' : 'text-green-600'}`}>
                        {g.value > 0 ? '+' : ''}{g.value.toFixed(2)}%
                      </span>
                      <span className={`px-2 py-1 rounded text-xs font-semibold ${
                        g.status === 'ok' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                      }`}>
                        {g.status === 'ok' ? '✓ OK' : '✗ BREACH'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {exp.status === 'completed' && (
              <div className="mt-4 pt-4 border-t">
                <p className="text-sm font-semibold text-gray-700">Decision: <span className="text-orange-600">{exp.decision}</span></p>
              </div>
            )}

            {exp.sequential && (
              <div className="mt-4 pt-4 border-t">
                <div className="flex items-center gap-2">
                  {exp.sequential.pValue < exp.sequential.boundary ? (
                    <>
                      <CheckCircle className="text-green-600" size={18} />
                      <p className="text-sm text-green-600">
                        Can stop early: p-value ({exp.sequential.pValue.toFixed(6)}) &lt; boundary ({exp.sequential.boundary.toFixed(6)})
                      </p>
                    </>
                  ) : (
                    <>
                      <AlertCircle className="text-blue-600" size={18} />
                      <p className="text-sm text-blue-600">
                        Continue running: {(exp.infoFraction * 100).toFixed(0)}% of planned sample
                      </p>
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );

  const renderRecommendationsTab = () => (
    <div className="p-6 space-y-6">
      {/* User Profile Header */}
      <div className="bg-gradient-to-r from-blue-500 to-purple-600 text-white p-6 rounded-lg">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h2 className="text-2xl font-bold mb-2">Personalized Feed</h2>
            <p className="text-blue-100">Tailored recommendations for user {userProfile.userId}</p>
          </div>
          <div className="text-right">
            <p className="text-4xl font-bold mb-1">{userProfile.engagementScore.toFixed(1)}</p>
            <p className="text-blue-100">Engagement Score</p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-blue-100 text-sm">Cohort</p>
            <p className="text-lg font-semibold">{userProfile.cohort}</p>
          </div>
          <div>
            <p className="text-blue-100 text-sm">Last Active</p>
            <p className="text-lg font-semibold">{userProfile.lastActive}</p>
          </div>
          <div>
            <p className="text-blue-100 text-sm">Goals</p>
            <p className="text-lg font-semibold">{userProfile.goals.join(', ')}</p>
          </div>
        </div>
      </div>

      {/* Recommendations Feed */}
      <div className="space-y-3">
        {recommendations.map((rec) => (
          <div key={rec.id} className="bg-white p-4 rounded-lg border border-gray-200 hover:shadow-md transition-shadow">
            <div className="flex justify-between items-start mb-2">
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-gray-900">{rec.title}</h3>
                <p className="text-sm text-gray-600 mt-1">{rec.description}</p>
              </div>
              <div className="ml-4 flex flex-col items-end">
                <div className="text-right mb-2">
                  <p className="text-3xl font-bold text-green-600">{(rec.relevance * 100).toFixed(0)}%</p>
                  <p className="text-xs text-gray-500">Relevance</p>
                </div>
                <div className={`px-3 py-1 rounded text-xs font-semibold ${
                  rec.type === 'workout' ? 'bg-orange-100 text-orange-800' :
                  rec.type === 'article' ? 'bg-blue-100 text-blue-800' :
                  'bg-purple-100 text-purple-800'
                }`}>
                  {rec.type.charAt(0).toUpperCase() + rec.type.slice(1)}
                </div>
              </div>
            </div>

            <div className="flex gap-4 mt-3 pt-3 border-t">
              <div className="flex items-center gap-1">
                <span className="text-xs text-gray-500">Category:</span>
                <span className="text-sm font-semibold text-gray-700">{rec.category}</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="text-xs text-gray-500">Difficulty:</span>
                <span className="text-sm font-semibold text-gray-700">{rec.difficulty}</span>
              </div>
              <div className="flex items-center gap-1 ml-auto">
                <span className="text-xs text-gray-600 italic">{rec.reason}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Recommendation Model Info */}
      <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
        <h3 className="text-sm font-semibold text-gray-900 mb-2">How are these recommended?</h3>
        <p className="text-sm text-gray-600">
          Recommendations are personalized using a multi-stage ranking model:
        </p>
        <ol className="text-sm text-gray-600 mt-2 ml-4 space-y-1">
          <li>1. <span className="font-semibold">Content Filtering</span>: Match user's stated goals and categories</li>
          <li>2. <span className="font-semibold">Collaborative Filtering</span>: Find similar users' preferences</li>
          <li>3. <span className="font-semibold">Engagement Model</span>: Score based on engagement stage</li>
          <li>4. <span className="font-semibold">Diversity</span>: Avoid recommending too similar items</li>
          <li>5. <span className="font-semibold">Freshness</span>: Balance new content with proven favorites</li>
        </ol>
      </div>
    </div>
  );

  // =========================================================================
  // MAIN RENDER
  // =========================================================================

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                Engagement & Personalization Engine
              </h1>
              <p className="text-gray-600 mt-1">
                Real-time dashboard for user engagement, experiments, and personalization
              </p>
            </div>
            <TrendingUp className="text-green-600" size={40} />
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex gap-8">
            <button
              onClick={() => setActiveTab('engagement')}
              className={`py-4 px-2 border-b-2 font-semibold transition-colors ${
                activeTab === 'engagement'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-600 hover:text-gray-900'
              }`}
            >
              Engagement Overview
            </button>
            <button
              onClick={() => setActiveTab('experiments')}
              className={`py-4 px-2 border-b-2 font-semibold transition-colors ${
                activeTab === 'experiments'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-600 hover:text-gray-900'
              }`}
            >
              Experiments
            </button>
            <button
              onClick={() => setActiveTab('recommendations')}
              className={`py-4 px-2 border-b-2 font-semibold transition-colors ${
                activeTab === 'recommendations'
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-600 hover:text-gray-900'
              }`}
            >
              Recommendations
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto">
        {activeTab === 'engagement' && renderEngagementTab()}
        {activeTab === 'experiments' && renderExperimentsTab()}
        {activeTab === 'recommendations' && renderRecommendationsTab()}
      </div>

      {/* Footer */}
      <div className="bg-gray-50 border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-6 py-6 text-center text-sm text-gray-600">
          <p>
            Dashboard data updated in real-time from Snowflake. Experiments managed by FastAPI service.
            Recommendations served from feature store.
          </p>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
