/**
 * API client exports
 *
 * Re-exports API functions from services/api for backwards compatibility with tests.
 */

export {
  getNeighbors,
  searchSemantic,
  getArticle,
  autocomplete,
  apiClient,
} from '../services/api';
