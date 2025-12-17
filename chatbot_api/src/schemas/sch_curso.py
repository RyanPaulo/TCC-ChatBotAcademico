from typing import Optional, List, Union
from pydantic import BaseModel, Field, field_validator
from datetime import timedelta
import uuid
import re

class CursoBase(BaseModel):
    nome_curso: str
    periodo: int
    modalidade: List[str] = Field(default_factory=list)
    formacao: str
    descricao: str
    carga_horaria: Union[int, str, timedelta] = Field(..., description="Carga horária em horas (pode ser número, string ou timedelta)")

    @field_validator('carga_horaria', mode='before')
    @classmethod
    def parse_carga_horaria(cls, v):
        """
        Converte carga_horaria para timedelta.
        Aceita: int (horas), str (horas como string), timedelta, ou formato PostgreSQL INTERVAL (HH:MM:SS).
        """
        if isinstance(v, timedelta):
            return v
        if v is None:
            return None
        
        if isinstance(v, str):
            if ':' in v:
                try:
                    parts = v.split()
                    if len(parts) > 1 and 'days' in parts:
                        days = int(parts[0])
                        time_part = parts[2] if len(parts) > 2 else "0:0:0"
                        h, m, s = map(int, time_part.split(':'))
                        return timedelta(days=days, hours=h, minutes=m, seconds=s)
                    else:
                        time_parts = v.split(':')
                        if len(time_parts) == 3:
                            h = int(time_parts[0])
                            m = int(time_parts[1])
                            s_part = time_parts[2].split('.')
                            s = int(s_part[0])
                            microseconds = int(float('0.' + s_part[1]) * 1000000) if len(s_part) > 1 else 0
                            return timedelta(hours=h, minutes=m, seconds=s, microseconds=microseconds)
                except (ValueError, IndexError):
                    pass
            
            try:
                horas = int(v)
                return timedelta(hours=horas)
            except ValueError:
                raise ValueError(f"Carga horária inválida: {v}. Deve ser um número (horas), timedelta ou formato INTERVAL (HH:MM:SS).")
        
        try:
            horas = int(v)
            return timedelta(hours=horas)
        except (ValueError, TypeError):
            raise ValueError(f"Carga horária inválida: {v}. Deve ser um número (horas), timedelta ou formato INTERVAL (HH:MM:SS).")

class CursoCreate(CursoBase):
    pass

class Curso(BaseModel):
    id_curso: uuid.UUID
    nome_curso: str
    periodo: int
    modalidade: List[str] = Field(default_factory=list)
    formacao: str
    descricao: str
    carga_horaria: int = Field(..., description="Carga horária em horas (número inteiro)")

    @field_validator('carga_horaria', mode='before')
    @classmethod
    def parse_carga_horaria_response(cls, v):
        if isinstance(v, int):
            return v
        if v is None:
            return None
        if isinstance(v, timedelta):
            return int(v.total_seconds() // 3600)
        if isinstance(v, str):
            v_str = v.strip()
            if v_str.startswith('P'):
                try:
                    days_match = re.search(r'(\d+)D', v_str)
                    hours_match = re.search(r'(\d+)H', v_str)
                    minutes_match = re.search(r'(\d+)M', v_str)
                    
                    days = int(days_match.group(1)) if days_match else 0
                    hours = int(hours_match.group(1)) if hours_match else 0
                    minutes = int(minutes_match.group(1)) if minutes_match else 0
                    
                    total_hours = (days * 24) + hours + (minutes / 60)
                    return int(total_hours)
                except (ValueError, AttributeError):
                    pass
            elif ':' in v_str:
                try:
                    horas_str = v_str.split(':')[0]
                    return int(horas_str)
                except ValueError:
                    pass
            try:
                return int(v_str)
            except ValueError:
                pass
        raise ValueError(f"Não foi possível converter carga_horaria '{v}' para horas (int)")

    class Config:
        from_attributes = True


class CursoUpadate(BaseModel):
    nome_curso: Optional[str] = None
    periodo: Optional[int] = None
    modalidade: Optional[List[str]] = Field(default_factory=list)
    formacao: Optional[str] = None
    descricao: Optional[str] = None
    carga_horaria: Optional[Union[int, str, timedelta]] = Field(None, description="Carga horária em horas (pode ser número, string ou timedelta)")

    @field_validator('carga_horaria', mode='before')
    @classmethod
    def parse_carga_horaria_update(cls, v):
        """
        Converte carga_horaria para timedelta.
        Aceita: int (horas), str (horas como string), timedelta, ou formato PostgreSQL INTERVAL (HH:MM:SS).
        """
        if v is None:
            return None
        if isinstance(v, timedelta):
            return v
        
        if isinstance(v, str):
            if ':' in v:
                try:
                    parts = v.split()
                    if len(parts) > 1 and 'days' in parts:
                        days = int(parts[0])
                        time_part = parts[2] if len(parts) > 2 else "0:0:0"
                        h, m, s = map(int, time_part.split(':'))
                        return timedelta(days=days, hours=h, minutes=m, seconds=s)
                    else:
                        time_parts = v.split(':')
                        if len(time_parts) == 3:
                            h = int(time_parts[0])
                            m = int(time_parts[1])
                            s_part = time_parts[2].split('.')
                            s = int(s_part[0])
                            microseconds = int(float('0.' + s_part[1]) * 1000000) if len(s_part) > 1 else 0
                            return timedelta(hours=h, minutes=m, seconds=s, microseconds=microseconds)
                except (ValueError, IndexError):
                    pass
            
            try:
                horas = int(v)
                return timedelta(hours=horas)
            except ValueError:
                raise ValueError(f"Carga horária inválida: {v}. Deve ser um número (horas), timedelta ou formato INTERVAL (HH:MM:SS).")
        
        try:
            horas = int(v)
            return timedelta(hours=horas)
        except (ValueError, TypeError):
            raise ValueError(f"Carga horária inválida: {v}. Deve ser um número (horas), timedelta ou formato INTERVAL (HH:MM:SS).")