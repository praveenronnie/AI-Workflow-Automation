import { PlatformAdapter } from './platformAdapter';
import { useStore } from '@/store/useStore';

/**
 * Generic, data-driven platform adapter.
 *
 * All domain knowledge (section templates, field aliases, intents) comes from
 * the backend domain registry (`GET /domains` via the message bus) — there are
 * no hardcoded domain fallbacks, so any domain registered in the backend works
 * without frontend changes. Platform-specific behaviour lives in the browser
 * extension's adapter JSON configs, not here.
 */
export class OpenquireAdapter extends PlatformAdapter {
  constructor(domain: string) {
    super(domain);
  }

  /** Get section templates for the current domain (backend-driven). */
  async getSectionTemplates(): Promise<Record<string, any>> {
    const domainInfo = this.getDomainInfo();
    return domainInfo.sectionTemplates ?? {};
  }

  /** Get field aliases for intent detection (backend-driven). */
  async getFieldAliases(): Promise<Record<string, string[]>> {
    const domainInfo = this.getDomainInfo();
    return domainInfo.fieldAliases ?? {};
  }

  /** Get domain-specific intents from the discovered domain metadata. */
  async getDomainIntents(): Promise<string[]> {
    const domainInfo = this.getDomainInfo();
    return domainInfo.intents ?? [];
  }

  /** Aggregate raw form schema with platform-specific data. */
  async aggregateFormSchema(rawSchema: Record<string, any>): Promise<Record<string, any>> {
    const augmented = { ...rawSchema };

    const sectionTemplates = await this.getSectionTemplates();
    const fieldAliases = await this.getFieldAliases();

    augmented.platform_sections = Object.values(sectionTemplates);
    augmented.field_aliases = fieldAliases;

    return augmented;
  }

  /** Get mapping configuration for a field. */
  async getMappingConfig(_fieldId: string): Promise<{
    sourceKey?: string;
    value?: string;
    confidence?: number;
  }> {
    return {
      sourceKey: undefined,
      value: undefined,
      confidence: 0,
    };
  }
}

/**
 * Get the OpenQuire adapter for the currently-selected domain.
 *
 * Domain-agnostic: the adapter is constructed for whatever domain slug the
 * store holds; there is no hardcoded list of supported domains.
 */
export function getOpenquireAdapter(): OpenquireAdapter | null {
  const domain = useStore.getState().domain;
  if (!domain) return null;
  return new OpenquireAdapter(domain);
}