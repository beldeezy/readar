import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { OnboardingPayload, BookPreference, RevenueRange } from '../api/types';
import Input from '../components/Input';
import Button from '../components/Button';
import Card from '../components/Card';
import MultiSelect from '../components/MultiSelect';
import { BookCalibrationStep } from '../components/Onboarding/BookCalibrationStep';
import { ReadingHistoryUploadStep } from '../components/Onboarding/ReadingHistoryUploadStep';
import { useAuth } from '../contexts/AuthContext';
import { DEV_TEST_USER_ID } from '../api/constants';
import { ECONOMIC_SECTORS, INDUSTRIES, INDUSTRIES_BY_SECTOR, BUSINESS_MODELS, AREAS_OF_BUSINESS } from '../config/onboarding';
import './OnboardingPage.css';

const BUSINESS_STAGES = [
  { value: 'idea', label: 'Idea Stage' },
  { value: 'pre-revenue', label: 'Pre-Revenue' },
  { value: 'early-revenue', label: 'Early Revenue' },
  { value: 'scaling', label: 'Scaling' },
] as const;

const REVENUE_OPTIONS: { value: RevenueRange; label: string }[] = [
  { value: "pre_revenue", label: "Pre-revenue" },
  { value: "lt_100k", label: "<$100k" },
  { value: "100k_300k", label: "$100k–$300k" },
  { value: "300k_500k", label: "$300k–$500k" },
  { value: "500k_1m", label: "$500k–$1m" },
  { value: "1m_3m", label: "$1m–$3m" },
  { value: "3m_5m", label: "$3m–$5m" },
  { value: "5m_10m", label: "$5m–$10m" },
  { value: "10m_30m", label: "$10m–$30m" },
  { value: "30m_100m", label: "$30m–$100m" },
  { value: "100m_plus", label: "$100m+" },
];

export default function OnboardingPage() {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const { user: authUser } = useAuth() ?? { user: null };
  
  // Use auth user ID if available, otherwise fallback to dev test user ID
  const userId = authUser?.id ?? DEV_TEST_USER_ID;
  console.log("Onboarding userId:", userId);

  const [formData, setFormData] = useState<Partial<OnboardingPayload & { 
    business_models: string[];
    challenges_and_blockers: string;
    economic_sector?: string;
    entrepreneur_status?: string;
  }>>({
    areas_of_business: [],
    business_models: [],
    challenges_and_blockers: '',
    book_preferences: [],
  });

  // Compute filtered industries based on selected sector
  const selectedSector = (formData as any).economic_sector || "";
  const allowedIndustryValues = selectedSector ? (INDUSTRIES_BY_SECTOR[selectedSector] || []) : [];
  const filteredIndustries = selectedSector
    ? INDUSTRIES.filter((i) => allowedIndustryValues.includes(i.value))
    : [];

  const updateField = (field: keyof OnboardingPayload, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const updateArrayField = (field: 'areas_of_business' | 'business_models', values: string[]) => {
    setFormData((prev) => ({ ...prev, [field]: values }));
  };

  const handleNext = () => {
    if (step === 1 && !formData.full_name) {
      setError('Full name is required');
      return;
    }
    if (step === 1 && !(formData as any).economic_sector) {
      setError("Economic sector is required");
      return;
    }
    if (step === 1 && !formData.industry) {
      setError("Industry is required");
      return;
    }
    if (step === 2 && (!formData.business_models || formData.business_models.length === 0)) {
      setError('Business model is required');
      return;
    }
    if (step === 2 && !formData.business_stage) {
      setError('Business stage is required');
      return;
    }
    if (step === 3 && !formData.challenges_and_blockers) {
      setError('Please describe your challenges and blockers');
      return;
    }
    setError('');
    setStep(step + 1);
  };

  const handleUpdate = (patch: Partial<OnboardingPayload>) => {
    setFormData((prev) => ({ ...prev, ...patch }));
  };

  const handleSubmit = async () => {
    console.log("handleSubmit start");
    
    if (!formData.full_name || !(formData as any).economic_sector || !formData.industry || !formData.business_models || formData.business_models.length === 0 || !formData.business_stage || !formData.challenges_and_blockers) {
      setError('Please complete all required fields');
      return;
    }

    setLoading(true);
    setError('');

    try {
      // TEMP: Map form data to backend payload format
      // - business_models array -> business_model string (comma-separated for backward compatibility)
      // - challenges_and_blockers -> both biggest_challenge and blockers fields
      const payload: OnboardingPayload = {
        ...formData,
        business_model: formData.business_models?.join(', ') || '', // Join array into string for backend compatibility
        biggest_challenge: formData.challenges_and_blockers || '', // Populate both fields with combined value
        blockers: formData.challenges_and_blockers || '', // TEMP: Until backend schema is updated to single field
        book_preferences: formData.book_preferences || [],
      } as OnboardingPayload;

      await apiClient.saveOnboarding(payload, userId);
      console.log("saveOnboarding done, navigating to loading");
      // Navigate to loading page
      navigate(`/recommendations/loading?userId=${encodeURIComponent(userId)}&limit=5`);
    } catch (err: any) {
      // The API client now throws Error with backend detail message
      setError(err.message || 'Failed to save onboarding');
    } finally {
      setLoading(false);
    }
  };


  return (
    <div className="readar-onboarding-page">
      <div className="container">
        <Card variant="elevated" className="readar-onboarding-card">
          <div className="readar-progress-bar">
            <div className="readar-progress" style={{ width: `${(step / 5) * 100}%` }} />
          </div>
          <h1 className="readar-onboarding-title">Tell us about yourself</h1>

          {error && <div className="readar-onboarding-error">{error}</div>}

        {/* Step 1: You & Your Venture */}
        {step === 1 && (
          <div className="readar-step-content">
            <h2 className="readar-step-title">You & Your Venture</h2>
            <Input
              label="Full Name *"
              type="text"
              value={formData.full_name || ''}
              onChange={(e) => updateField('full_name', e.target.value)}
              placeholder="John Doe"
              required
            />
            <div className="readar-input-group">
              <label className="readar-input-label">Entrepreneur Status</label>
              <select
                className="readar-input readar-select"
                value={(formData as any).entrepreneur_status || ""}
                onChange={(e) => updateField('entrepreneur_status' as any, e.target.value)}
              >
                <option value="">Select status</option>
                <option value="considering">Considering</option>
                <option value="part_time">Part-time</option>
                <option value="full_time">Full-time</option>
              </select>
            </div>
            <Input
              label="Location"
              type="text"
              value={formData.location || ''}
              onChange={(e) => updateField('location', e.target.value)}
              placeholder="San Francisco, CA"
            />
            <div className="readar-input-group">
              <label className="readar-input-label">Economic Sector *</label>
              <select
                className="readar-input readar-select"
                value={(formData as any).economic_sector || ""}
                onChange={(e) => {
                  // set sector + reset industry
                  setFormData((prev) => ({
                    ...prev,
                    economic_sector: e.target.value,
                    industry: "", // reset industry when sector changes
                  }));
                }}
                required
              >
                <option value="">Select economic sector</option>
                {ECONOMIC_SECTORS.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="readar-input-group">
              <label className="readar-input-label">Industry *</label>
              <select
                className="readar-input readar-select"
                value={formData.industry || ""}
                onChange={(e) => updateField("industry", e.target.value)}
                disabled={!((formData as any).economic_sector)}
                required
              >
                <option value="">{(formData as any).economic_sector ? "Select industry" : "Select economic sector first"}</option>
                {filteredIndustries.map((industry) => (
                  <option key={industry.value} value={industry.value}>
                    {industry.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}

        {/* Step 2: Business Basics */}
        {step === 2 && (
          <div className="readar-step-content">
            <h2 className="readar-step-title">Business Basics</h2>
            <MultiSelect
              label="Business Model *"
              options={BUSINESS_MODELS}
              selectedValues={formData.business_models || []}
              onChange={(values) => updateArrayField('business_models', values)}
              placeholder="Select business model(s)..."
              required
            />
            <div className="readar-input-group">
              <label className="readar-input-label">Business Stage *</label>
              <select
                className="readar-input readar-select"
                value={formData.business_stage || ''}
                onChange={(e) => updateField('business_stage', e.target.value as any)}
                required
              >
                <option value="">Select stage</option>
                {BUSINESS_STAGES.map((stage) => (
                  <option key={stage.value} value={stage.value}>
                    {stage.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="readar-input-group">
              <label className="readar-input-label">Gross Revenue</label>
              <select
                className="readar-input readar-select"
                value={formData.current_gross_revenue || ''}
                onChange={(e) => updateField('current_gross_revenue', e.target.value || undefined)}
              >
                <option value="">Select one</option>
                {REVENUE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <Input
              label="Organization Size"
              type="text"
              value={formData.org_size || ''}
              onChange={(e) => updateField('org_size', e.target.value)}
              placeholder="1-10, 11-50, etc."
            />
            <div className="readar-input-group">
              <label className="readar-input-label">Business Experience</label>
              <textarea
                className="readar-input readar-textarea"
                value={formData.business_experience || ''}
                onChange={(e) => updateField('business_experience', e.target.value)}
                placeholder="Tell us about your experience..."
                rows={4}
              />
            </div>
          </div>
        )}

        {/* Step 3: Work Focus & Challenges */}
        {step === 3 && (
          <div className="readar-step-content">
            <h2 className="readar-step-title">Work Focus & Challenges</h2>
            <MultiSelect
              label="Areas of Business Focus"
              options={AREAS_OF_BUSINESS}
              selectedValues={formData.areas_of_business || []}
              onChange={(values) => updateArrayField('areas_of_business', values)}
              placeholder="Select areas of focus..."
            />
            <div className="readar-input-group">
              <label className="readar-input-label">Vision (6-12 months)</label>
              <textarea
                className="readar-input readar-textarea"
                value={formData.vision_6_12_months || ''}
                onChange={(e) => updateField('vision_6_12_months', e.target.value)}
                placeholder="Where do you want to be in 6-12 months?"
                rows={4}
              />
            </div>
            <div className="readar-input-group">
              <label className="readar-input-label">What are your biggest challenges and blockers right now? *</label>
              <p style={{ 
                fontSize: 'var(--rd-font-size-sm)', 
                color: 'var(--rd-muted)', 
                marginBottom: '0.5rem',
                marginTop: '0.25rem'
              }}>
                Describe what's getting in the way of your progress.
              </p>
              <textarea
                className="readar-input readar-textarea"
                value={formData.challenges_and_blockers || ''}
                onChange={(e) => updateField('challenges_and_blockers', e.target.value)}
                placeholder="What are your biggest challenges and blockers right now?"
                rows={4}
                required
              />
              {/* TEMP: This combined field populates both biggest_challenge and blockers in the payload
                  until the backend schema is updated to a single combined field */}
            </div>
          </div>
        )}

        {/* Step 4: Book Calibration */}
        {step === 4 && (
          <BookCalibrationStep
            initialPreferences={formData.book_preferences as BookPreference[] | undefined}
            onChangePreferences={(prefs) => {
              handleUpdate({ book_preferences: prefs });
            }}
            onBack={() => setStep(step - 1)}
            onContinue={(prefs) => {
              handleUpdate({ book_preferences: prefs });
              setStep(step + 1);
            }}
          />
        )}

        {/* Step 5: Reading History Upload */}
        {step === 5 && (
          <ReadingHistoryUploadStep
            userId={userId}
            onBack={() => setStep(step - 1)}
            onSkip={handleSubmit}
            onNext={handleSubmit}
          />
        )}

        {/* Only show step actions for steps 1-3 (steps 4-5 have their own buttons) */}
        {step < 4 && (
          <div
            className="readar-step-actions"
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '0.75rem',
              marginTop: '1.25rem',
            }}
          >
            {step > 1 && (
              <Button variant="ghost" delayMs={140} onClick={() => setStep(step - 1)}>
                Back
              </Button>
            )}
            {step < 3 ? (
              <Button variant="primary" onClick={handleNext} delayMs={140}>
                Next
              </Button>
            ) : (
              <Button variant="primary" onClick={handleNext} disabled={loading} delayMs={140}>
                Next
              </Button>
            )}
          </div>
        )}
        </Card>
      </div>
    </div>
  );
}

