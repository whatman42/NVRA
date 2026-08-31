"""Hardware-aware workload profiles designed for 8GB DDR3 minimum hosts."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class HardwareResourceProfile(str,Enum):
    LOW_END_8GB="LOW_END_8GB"
    RECOMMENDED_16GB="RECOMMENDED_16GB"
    PERFORMANCE_32GB="PERFORMANCE_32GB"
    GPU_64GB="GPU_64GB"

@dataclass(frozen=True)
class WorkloadPolicy:
    profile: HardwareResourceProfile
    max_workers:int
    max_parallel_models:int
    max_active_models:int
    inference_batch:int
    max_dataset_rows:int
    training_enabled:bool
    heavy_ml_inference:bool
    heavy_ml_training:bool
    agent_debate_rounds:int
    checkpoint_interval:int
    notes:tuple[str,...]=()

POLICIES={
HardwareResourceProfile.LOW_END_8GB:WorkloadPolicy(HardwareResourceProfile.LOW_END_8GB,1,1,6,64,100_000,True,False,False,1,1,("sequential training","tree models + numpy/scikit-learn","LLM advisory only, external provider","no resident torch training")),
HardwareResourceProfile.RECOMMENDED_16GB:WorkloadPolicy(HardwareResourceProfile.RECOMMENDED_16GB,2,2,10,128,250_000,True,True,False,2,1,("parallelism capped","CPU heavy models remain serialized")),
HardwareResourceProfile.PERFORMANCE_32GB:WorkloadPolicy(HardwareResourceProfile.PERFORMANCE_32GB,4,3,12,256,1_000_000,True,True,True,2,1,("heavy training only when pressure permits",)),
HardwareResourceProfile.GPU_64GB:WorkloadPolicy(HardwareResourceProfile.GPU_64GB,8,4,16,512,5_000_000,True,True,True,3,1,("GPU-aware workloads",)),
}

def recommend_profile(total_ram_mb:int,cpu_threads:int,gpu_available:bool=False)->HardwareResourceProfile:
    if total_ram_mb < 12_000: return HardwareResourceProfile.LOW_END_8GB
    if total_ram_mb < 28_000: return HardwareResourceProfile.RECOMMENDED_16GB
    if gpu_available and total_ram_mb>=56_000: return HardwareResourceProfile.GPU_64GB
    return HardwareResourceProfile.PERFORMANCE_32GB

def policy_for(profile:HardwareResourceProfile)->WorkloadPolicy: return POLICIES[profile]
