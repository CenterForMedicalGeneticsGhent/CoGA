import { useState, type FC, type FormEvent } from 'react';
import api from '../../lib/api';
import { getErrorMessage } from '../../lib/errorMessage';
import { useProjectCatalog } from '../../lib/reference';

const INHERITANCE_MODELS = ['', 'AD', 'AR', 'XLD', 'XLR', 'mitochondrial'];

const PedUpload: FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [projectId, setProjectId] = useState('');
  const [roiQuery, setRoiQuery] = useState('');
  const [inheritanceModel, setInheritanceModel] = useState('');
  const [obligateCarriers, setObligateCarriers] = useState('');
  const [provenCarriers, setProvenCarriers] = useState('');
  const [status, setStatus] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const { data: projects = [], isLoading: projectsLoading } = useProjectCatalog();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    if (roiQuery.trim() && !projectId) {
      setStatus('Select a project to resolve the ROI.');
      return;
    }
    const formData = new FormData();
    formData.append('file', file);
    if (roiQuery.trim()) formData.append('roi_query', roiQuery.trim());
    if (inheritanceModel) formData.append('inheritance_model', inheritanceModel);
    if (obligateCarriers.trim()) formData.append('obligate_carriers', obligateCarriers.trim());
    if (provenCarriers.trim()) formData.append('proven_carriers', provenCarriers.trim());
    const params = new URLSearchParams();
    if (projectId) params.set('project_id', projectId);
    setStatus('');
    setLoading(true);
    try {
      const queryString = params.toString();
      await api.post(`/ped/upload${queryString ? `?${queryString}` : ''}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setStatus('Upload successful');
    } catch (err: any) {
      if (err.response?.status === 409) {
        const overwrite = window.confirm(
          'Families already exist in database. Overwrite?'
        );
        if (overwrite) {
          try {
            params.set('overwrite', 'true');
            await api.post(`/ped/upload?${params.toString()}`, formData, {
              headers: { 'Content-Type': 'multipart/form-data' },
            });
            setStatus('Upload successful');
          } catch (overwriteError: unknown) {
            setStatus(getErrorMessage(overwriteError, 'Upload failed'));
          }
        } else {
          setStatus('Upload cancelled');
        }
      } else {
        setStatus(getErrorMessage(err, 'Upload failed'));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-shell-narrow">
      <div className="surface-card page-top-card space-y-5">
        <div className="space-y-2">
          <p className="page-kicker">Upload</p>
          <h1 className="section-title">Upload PED File</h1>
          <p className="section-copy">
            Import an existing PED file when the family structure is already defined.
          </p>
        </div>
        <form onSubmit={handleSubmit} className="field-grid">
          <label className="field-label">
            Project
            <select
              value={projectId}
              disabled={loading || projectsLoading}
              onChange={(event) => setProjectId(event.target.value)}
            >
              <option value="">
                {projectsLoading ? 'Loading projects...' : 'No project selected'}
              </option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field-label">
            PED file
            <input
              type="file"
              accept=".ped"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </label>
          <label className="field-label">
            ROI gene or region
            <input
              value={roiQuery}
              onChange={(event) => setRoiQuery(event.target.value)}
              placeholder="CFTR or chr7:117120000-117310000"
            />
          </label>
          <label className="field-label">
            Inheritance model
            <select
              value={inheritanceModel}
              onChange={(event) => setInheritanceModel(event.target.value)}
            >
              {INHERITANCE_MODELS.map((model) => (
                <option key={model || 'none'} value={model}>
                  {model || 'Not specified'}
                </option>
              ))}
            </select>
          </label>
          <label className="field-label">
            Obligate carriers
            <input
              value={obligateCarriers}
              onChange={(event) => setObligateCarriers(event.target.value)}
              placeholder="Sample IDs, comma-separated"
            />
          </label>
          <label className="field-label">
            Proven carriers
            <input
              value={provenCarriers}
              onChange={(event) => setProvenCarriers(event.target.value)}
              placeholder="Sample IDs, comma-separated"
            />
          </label>
          <button type="submit" className="w-full justify-center" disabled={loading}>
            Upload
          </button>
        </form>
      {loading && (
          <div className="loading-spinner" />
      )}
        {status && <p className="form-status text-center">{status}</p>}
      </div>
    </div>
  );
};

export default PedUpload;
