using System;
using System.Collections.Generic;
using System.Text;
using UnityEngine;

namespace Assets.Scripts.Resources
{
	public abstract class ResourceHandler : MonoBehaviour, IResourceHandler
	{
		public abstract void HandleBytes(byte[] data, Guid128 guid, string strFilePath);

		public abstract IEnumerable<Resource> GetResources();
	}

	public interface IResourceHandler
	{
		public void HandleBytes(byte[] data, Guid128 guid, string strFilePath);

		public IEnumerable<Resource> GetResources();
	}

	[Serializable]
	public abstract class Resource
	{
		public string STRFile;
	    public Guid128 GUID;
    }
}
