import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  getHealth,
  createWorkflow,
  getWorkflow,
  approveWorkflow,
  rejectWorkflow,
  getWorkflowAudit,
  ApiError,
} from '../lib/api';

describe('API Client (frontend/lib/api.ts)', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    global.fetch = vi.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('getHealth fetches /api/health and returns JSON data', async () => {
    const mockHealth = { status: 'ok', service: 'ai-operations-agent', version: '0.1.0' };
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockHealth,
    });

    const result = await getHealth();
    expect(result).toEqual(mockHealth);
    expect(global.fetch).toHaveBeenCalledWith('/api/health', expect.objectContaining({ method: 'GET' }));
  });

  it('createWorkflow posts request payload to /api/workflows', async () => {
    const mockWorkflow = {
      workflow_id: 'wf_test123',
      request: 'Onboard Acme Corp',
      status: 'WAITING_FOR_APPROVAL',
      tasks: [],
      tool_results: [],
      artifacts: [],
      approvals: [],
      errors: [],
      audit_events: [],
      created_at: '2026-09-13T12:00:00Z',
      updated_at: '2026-09-13T12:00:00Z',
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockWorkflow,
    });

    const result = await createWorkflow('Onboard Acme Corp');
    expect(result.workflow_id).toBe('wf_test123');
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/workflows',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ request: 'Onboard Acme Corp' }),
      })
    );
  });

  it('getWorkflow fetches workflow state by ID', async () => {
    const mockWorkflow = {
      workflow_id: 'wf_test123',
      request: 'Onboard Acme',
      status: 'COMPLETED',
      tasks: [],
      tool_results: [],
      artifacts: [],
      approvals: [],
      errors: [],
      audit_events: [],
      created_at: '2026-09-13T12:00:00Z',
      updated_at: '2026-09-13T12:00:00Z',
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockWorkflow,
    });

    const result = await getWorkflow('wf_test123');
    expect(result.workflow_id).toBe('wf_test123');
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/workflows/wf_test123',
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('approveWorkflow sends approval decision payload', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        workflow_id: 'wf_test123',
        status: 'COMPLETED',
      }),
    });

    const result = await approveWorkflow('wf_test123', 'Looks solid');
    expect(result.status).toBe('COMPLETED');
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/workflows/wf_test123/approve',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ reason: 'Looks solid' }),
      })
    );
  });

  it('rejectWorkflow sends rejection payload', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        workflow_id: 'wf_test123',
        status: 'FAILED',
      }),
    });

    const result = await rejectWorkflow('wf_test123', 'Revision needed');
    expect(result.status).toBe('FAILED');
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/workflows/wf_test123/reject',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ reason: 'Revision needed' }),
      })
    );
  });

  it('getWorkflowAudit retrieves audit response', async () => {
    const mockAudit = {
      workflow_id: 'wf_test123',
      audit_events: [{ event_type: 'workflow_created', timestamp: '2026-09-13T12:00:00Z', details: {} }],
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockAudit,
    });

    const result = await getWorkflowAudit('wf_test123');
    expect(result.workflow_id).toBe('wf_test123');
    expect(result.audit_events.length).toBe(1);
  });

  it('safely extracts error detail from JSON responses', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: async () => ({ detail: 'No pending approval request found.' }),
    });

    await expect(approveWorkflow('wf_123')).rejects.toThrow('No pending approval request found.');
  });

  it('falls back gracefully when error response is not JSON', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 502,
      statusText: 'Bad Gateway',
      json: async () => { throw new Error('Not JSON'); },
    });

    await expect(getHealth()).rejects.toThrow('HTTP error 502: Bad Gateway');
  });
});
