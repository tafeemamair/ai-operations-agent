'use client';

import React from 'react';
import { WorkflowState } from '../lib/types';

interface ArtifactsViewerProps {
  workflow: WorkflowState;
}

export default function ArtifactsViewer({ workflow }: ArtifactsViewerProps) {
  const { artifacts, tool_results } = workflow;

  if (!artifacts || artifacts.length === 0) {
    return (
      <div className="card" data-testid="artifacts-empty">
        <h3 className="card-title">3. Generated Deliverables & Artifacts</h3>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          No artifacts generated yet. Run a workflow to view operational outputs.
        </p>
      </div>
    );
  }

  // Find specific tool results if available
  const briefResult = tool_results.find(
    (r) => r.tool_name === 'create_company_brief' && r.data
  );
  const checklistResult = tool_results.find(
    (r) => r.tool_name === 'create_onboarding_checklist' && r.data
  );
  const emailResult = tool_results.find(
    (r) => r.tool_name === 'draft_welcome_email' && r.data
  );

  const briefArtifact = artifacts.find((a) => a.artifact_type === 'company_brief');
  const checklistArtifact = artifacts.find((a) => a.artifact_type === 'onboarding_checklist');
  const emailArtifact = artifacts.find((a) => a.artifact_type === 'welcome_email_draft');
  const researchArtifact = artifacts.find((a) => a.artifact_type === 'company_research');

  return (
    <div className="card" data-testid="artifacts-viewer-card">
      <div className="card-header">
        <h3 className="card-title">3. Operational Artifacts & Deliverables</h3>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          {artifacts.length} Artifact{artifacts.length === 1 ? '' : 's'} Created
        </span>
      </div>

      <div className="artifacts-grid">
        {/* 1. Company Brief */}
        {(briefArtifact || briefResult) && (
          <div className="artifact-card" data-testid="artifact-brief-card">
            <div className="artifact-header">
              <span className="artifact-name">Company Operational Brief</span>
              <span className="artifact-type">Executive Doc</span>
            </div>
            {briefResult?.data ? (
              <div style={{ fontSize: '0.85rem', color: '#cbd5e1' }}>
                <p style={{ marginBottom: '0.4rem' }}>
                  <strong>Company:</strong> {briefResult.data.company_name}
                </p>
                <p style={{ marginBottom: '0.4rem' }}>
                  <strong>Industry:</strong> {briefResult.data.industry}
                </p>
                <div
                  className="artifact-content"
                  style={{ maxHeight: '180px' }}
                >
                  {briefResult.data.summary}
                </div>
                {briefResult.data.key_facts && (
                  <ul style={{ paddingLeft: '1.2rem', marginTop: '0.5rem', fontSize: '0.8rem' }}>
                    {briefResult.data.key_facts.map((fact: string, i: number) => (
                      <li key={i} style={{ color: 'var(--text-secondary)' }}>{fact}</li>
                    ))}
                  </ul>
                )}
              </div>
            ) : (
              <div className="artifact-content">
                {briefArtifact?.content || 'Brief content unavailable.'}
              </div>
            )}
          </div>
        )}

        {/* 2. Onboarding Checklist */}
        {(checklistArtifact || checklistResult) && (
          <div className="artifact-card" data-testid="artifact-checklist-card">
            <div className="artifact-header">
              <span className="artifact-name">Onboarding Procedure Checklist</span>
              <span className="artifact-type">Procedure</span>
            </div>
            {checklistResult?.data?.items ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {checklistResult.data.items.map((item: any) => (
                  <div
                    key={item.item_id}
                    style={{
                      padding: '0.4rem 0.6rem',
                      backgroundColor: 'var(--bg-main)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '4px',
                      fontSize: '0.8rem',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontWeight: 600, color: '#f1f5f9' }}>
                      <span style={{ color: '#10b981' }}>✓</span>
                      <span>{item.title}</span>
                    </div>
                    <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                      {item.description}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="artifact-content">
                {checklistArtifact?.content || 'Checklist content unavailable.'}
              </div>
            )}
          </div>
        )}

        {/* 3. Welcome Email Draft */}
        {(emailArtifact || emailResult) && (
          <div className="artifact-card" data-testid="artifact-email-card" style={{ gridColumn: '1 / -1' }}>
            <div className="artifact-header">
              <span className="artifact-name">Welcome Email Draft Preview</span>
              <span className="badge badge-waiting_for_approval">Sign-off Gated</span>
            </div>

            <div className="email-preview-container" style={{ margin: 0 }}>
              <div className="email-preview-header">
                <div className="email-header-row">
                  <span className="email-header-label">To:</span>
                  <span className="email-header-value mono">
                    {emailResult?.data?.recipient || 'operations-team@acme-corp.demo'}
                  </span>
                </div>
                <div className="email-header-row">
                  <span className="email-header-label">Subject:</span>
                  <span className="email-header-value">
                    {emailResult?.data?.subject || 'Welcome to AI Operations Agent Partnership'}
                  </span>
                </div>
              </div>
              <div className="email-preview-body mono">
                {emailResult?.data?.body || emailArtifact?.content || ''}
              </div>
            </div>
          </div>
        )}

        {/* 4. Company Research (if present and no brief) */}
        {researchArtifact && !briefArtifact && (
          <div className="artifact-card" data-testid="artifact-research-card">
            <div className="artifact-header">
              <span className="artifact-name">{researchArtifact.name}</span>
              <span className="artifact-type">Research Data</span>
            </div>
            <div className="artifact-content">{researchArtifact.content}</div>
          </div>
        )}
      </div>
    </div>
  );
}
