export type ApiStatus = "success" | "error";

export type ApiResponse<T> = {
  status: ApiStatus;
  message: string;
  data: T;
};