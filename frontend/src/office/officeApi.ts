import { createApiClient } from "../api";
import { officeApiTarget } from "./officeConfig";

export const { getBusSignal, useLiveStream } = createApiClient(officeApiTarget);
